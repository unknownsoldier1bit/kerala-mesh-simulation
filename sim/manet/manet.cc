// Disaster MANET simulation.
//
// A static ad-hoc 802.11b network of mesh nodes runs AODV, OLSR or DSDV while
// nodes and links fail (and sometimes come back) on a schedule read from a file.
// Everything that defines an experiment comes from three input files, written by
// experiments/gen.py, so the same topology, traffic and failures can be replayed
// with each protocol:
//
//   --topo    node_id,x,y                                  (metres)
//   --flows   flow_id,src,dst,start_s,stop_s,interval_s,payload_bytes
//             (a flow may have several rows: one per sending period)
//   --events  time_s,action,kind,a,b,group
//             action = fail | restore, kind = node | link (b = -1 for a node)
//
// Usage (normally called by experiments/run_experiment.py):
//   manet --protocol=olsr --topo=t.csv --flows=f.csv --events=e.csv --outDir=out
//
// Outputs (in --outDir):
//   packets.csv      one row per data packet: flow, seq, send and receive time,
//                    relay nodes on its path, and the last drop event seen
//   control.csv      routing control traffic per 1 s bin, by message type
//   events.csv       failure, restore and battery-depletion events as they happened
//   energy.csv       energy used per node and time spent in each radio state
//   routes.csv       OLSR/DSDV only: share of node pairs whose routing tables
//                    lead to the destination over links that currently work
//   discoveries.csv  AODV only: each route discovery, when it started and ended
//   stats.csv        run-level counters
//   flowmon.xml      FlowMonitor output (when --flowmon=true)
//   rtables-<t>.txt  every node's routing table at time t (when --rtDump is set)

#include "ns3/aodv-module.h"
#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/dsdv-module.h"
#include "ns3/energy-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/olsr-header.h"
#include "ns3/olsr-module.h"
#include "ns3/wifi-module.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <fstream>
#include <map>
#include <queue>
#include <set>
#include <sstream>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("Manet");

namespace
{

const uint16_t PORT_BASE = 10000; // flow f uses UDP port PORT_BASE + f
const uint16_t AODV_PORT = 654;
const uint16_t OLSR_PORT = 698;
const uint16_t DSDV_PORT = 269;

// ---- Network state ----
uint32_t g_n = 0;
double g_range = 150.0;
std::vector<Vector> g_pos;
NodeContainer g_nodes;
NetDeviceContainer g_devices;
Ipv4InterfaceContainer g_ifaces;
std::map<uint32_t, uint32_t> g_addrToNode; // IPv4 address (as integer) -> node id
std::vector<bool> g_alive;                 // radio on
std::vector<bool> g_depleted;              // battery ran out (never comes back)
std::set<std::pair<uint32_t, uint32_t>> g_blocked; // failed links, stored as (low id, high id)
std::string g_protocol = "aodv";
uint16_t g_routingPort = AODV_PORT;

// ---- Traffic ----
struct Segment
{
    uint32_t flow;
    double start;
    double stop;
    double interval;
};

struct PacketRecord
{
    double tx = -1;
    double rx = -1;
    std::vector<uint16_t> path; // relay nodes, in forwarding order
    int dropCode = 0;           // 0 = no drop seen
    int dropNode = -1;
    double dropTime = -1;
};

struct Flow
{
    uint32_t src;
    uint32_t dst;
    uint32_t payload; // UDP payload bytes, including the 12-byte sequence/timestamp header
    Ptr<Socket> tx;
    std::vector<PacketRecord> packets; // indexed by sequence number
};

std::vector<Flow> g_flows;
uint64_t g_suppressed = 0;   // sends skipped because the source's radio was off
uint64_t g_socketErrors = 0; // SendTo refused (no route known at the source)
uint64_t g_duplicates = 0;   // copies of a packet that the destination had already received

// ---- Routing control traffic, in 1 s bins ----
// Type columns: AODV  0 RREQ originated, 1 RREQ forwarded, 2 RREP, 3 RERR, 4 HELLO, 5 RREP-ACK
//               OLSR  0 HELLO messages, 1 TC messages, 2 MID, 3 HNA
const int N_TYPES = 6;
std::vector<uint64_t> g_ctrlPkts;
std::vector<uint64_t> g_ctrlBytes;
std::vector<std::array<uint64_t, N_TYPES>> g_ctrlTypes;
std::vector<uint64_t> g_macRetryDrops; // unicast frames given up after the retry limit (link breaks)
// A routing packet larger than the MTU leaves as IP fragments, and the IP Tx trace fires once
// per fragment (OLSR packs up to 64 messages into one packet, so this happens at high density).
// OnIpTx joins the fragments back together before reading the routing headers.
std::map<uint32_t, Ptr<Packet>> g_txFragments; // node -> payload of the fragments so far
std::map<uint32_t, uint32_t> g_txFragmentBytes;  // node -> IP-layer bytes of those fragments
std::map<uint32_t, uint16_t> g_txFragmentId;     // node -> IP identification of that packet
uint64_t g_fragmentedRoutingPackets = 0;

// ---- AODV route discoveries ----
struct Discovery
{
    uint32_t origin;
    uint32_t dst;
    double start;
    double end = -1;
    uint32_t attempts = 1;
};

std::vector<Discovery> g_discoveries;
// (origin, dst) -> index. Closed only by an RREP reaching the origin: a discovery that AODV abandons,
// or resolves another way (reverse route, HELLO), stays open and absorbs the next one for the same
// destination. experiments/metrics.py drops records longer than AODV's give-up time.
std::map<std::pair<uint32_t, uint32_t>, size_t> g_pendingDiscovery;

// ---- Events ----
struct FailureEvent
{
    double time;
    std::string action;
    std::string kind;
    int a;
    int b;
    std::string group;
};

std::vector<FailureEvent> g_eventLog;

// ---- Route validity samples (OLSR, DSDV) ----
std::vector<Ptr<olsr::RoutingProtocol>> g_olsr;
std::vector<Ptr<Ipv4RoutingProtocol>> g_routing;
std::ofstream g_routesOut;
double g_sampleInterval = 1.0;
double g_simTime = 300.0;

// ---- Energy ----
// Energy is computed from how long each radio spends in each PHY state, with the
// currents and voltage of ns-3's WifiRadioEnergyModel and BasicEnergySource defaults
// (checked in src/wifi/model/wifi-radio-energy-model.cc and
// src/energy/model/basic-energy-source.cc). This gives the same numbers as the ns-3
// energy framework at a fraction of the run time; --energyModel=ns3 runs the
// framework as well so the two can be compared.
double STATE_CURRENT_A[7] = {0.273, 0.273, 0.380, 0.313, 0.273, 0.033, 0.0};
// IDLE, CCA_BUSY, TX, RX, SWITCHING, SLEEP, OFF
const double SUPPLY_V = 3.0;
const double LOW_BATTERY_FRACTION = 0.10; // BasicEnergySource turns the radio off here
std::vector<std::array<double, 7>> g_stateTime;
std::vector<double> g_lastStateChange;
std::vector<double> g_initialJ; // 0 = unlimited battery
std::vector<Ptr<energy::EnergySource>> g_sources;
std::vector<Ptr<energy::DeviceEnergyModel>> g_radioModels;
std::vector<double> g_depletionTime;

uint32_t
Bin()
{
    auto b = static_cast<uint32_t>(Simulator::Now().GetSeconds());
    return std::min<uint32_t>(b, g_ctrlPkts.size() - 1);
}

std::pair<uint32_t, uint32_t>
LinkKey(uint32_t a, uint32_t b)
{
    return {std::min(a, b), std::max(a, b)};
}

int
NodeOfAddress(Ipv4Address addr)
{
    auto it = g_addrToNode.find(addr.Get());
    return it == g_addrToNode.end() ? -1 : static_cast<int>(it->second);
}

Ptr<WifiPhy>
PhyOf(uint32_t node)
{
    return DynamicCast<WifiNetDevice>(g_devices.Get(node))->GetPhy();
}

// True when nodes a and b can currently hear each other.
bool
LinkUp(uint32_t a, uint32_t b)
{
    if (!g_alive[a] || !g_alive[b] || g_blocked.count(LinkKey(a, b)))
    {
        return false;
    }
    return CalculateDistance(g_pos[a], g_pos[b]) <= g_range;
}

// ---------------------------------------------------------------------------
// Link failures: a propagation-loss stage that silences chosen node pairs.
// It sits after the distance-loss model in the loss chain, so a failed link
// behaves exactly like two nodes that are out of range of each other.
// ---------------------------------------------------------------------------
class LinkBlockLossModel : public PropagationLossModel
{
  public:
    static TypeId GetTypeId()
    {
        static TypeId tid = TypeId("ns3::LinkBlockLossModel")
                                .SetParent<PropagationLossModel>()
                                .SetGroupName("Propagation")
                                .AddConstructor<LinkBlockLossModel>();
        return tid;
    }

  private:
    double DoCalcRxPower(double txPowerDbm,
                         Ptr<MobilityModel> a,
                         Ptr<MobilityModel> b) const override
    {
        if (!g_blocked.empty())
        {
            uint32_t na = a->GetObject<Node>()->GetId();
            uint32_t nb = b->GetObject<Node>()->GetId();
            if (g_blocked.count(LinkKey(na, nb)))
            {
                return -1000.0;
            }
        }
        return txPowerDbm;
    }

    int64_t DoAssignStreams(int64_t) override
    {
        return 0;
    }
};

NS_OBJECT_ENSURE_REGISTERED(LinkBlockLossModel);

// ---------------------------------------------------------------------------
// Input files
// ---------------------------------------------------------------------------
std::vector<std::vector<std::string>>
ReadCsv(const std::string& path)
{
    std::ifstream in(path);
    if (!in)
    {
        NS_FATAL_ERROR("Can't open " << path);
    }
    std::vector<std::vector<std::string>> rows;
    std::string line;
    std::getline(in, line); // header
    while (std::getline(in, line))
    {
        if (line.empty())
        {
            continue;
        }
        std::vector<std::string> cells;
        std::stringstream ss(line);
        std::string cell;
        while (std::getline(ss, cell, ','))
        {
            cells.push_back(cell);
        }
        rows.push_back(cells);
    }
    return rows;
}

// ---------------------------------------------------------------------------
// Data packets
// ---------------------------------------------------------------------------

// Reads flow id and sequence number from an IP payload that starts with a UDP header.
bool
ParseData(Ptr<const Packet> payload, uint32_t& flow, uint32_t& seq)
{
    if (payload->GetSize() < 8 + 12)
    {
        return false;
    }
    Ptr<Packet> copy = payload->Copy();
    UdpHeader udp;
    copy->RemoveHeader(udp);
    uint16_t port = udp.GetDestinationPort();
    if (port < PORT_BASE || port >= PORT_BASE + g_flows.size())
    {
        return false;
    }
    SeqTsHeader st;
    copy->PeekHeader(st);
    flow = port - PORT_BASE;
    seq = st.GetSeq();
    return seq < g_flows[flow].packets.size();
}

void
RecordDrop(uint32_t flow, uint32_t seq, int code, uint32_t node)
{
    PacketRecord& r = g_flows[flow].packets[seq];
    r.dropCode = code;
    r.dropNode = node;
    r.dropTime = Simulator::Now().GetSeconds();
}

void
SendPacket(uint32_t f, double stop, double interval)
{
    Flow& flow = g_flows[f];
    if (g_alive[flow.src])
    {
        uint32_t seq = flow.packets.size();
        PacketRecord rec;
        rec.tx = Simulator::Now().GetSeconds();
        flow.packets.push_back(rec);
        SeqTsHeader header;
        header.SetSeq(seq);
        Ptr<Packet> packet = Create<Packet>(flow.payload - header.GetSerializedSize());
        packet->AddHeader(header);
        InetSocketAddress dest(g_ifaces.GetAddress(flow.dst), PORT_BASE + f);
        if (flow.tx->SendTo(packet, 0, dest) < 0)
        {
            g_socketErrors++;
            RecordDrop(f, seq, 1, flow.src);
        }
    }
    else
    {
        g_suppressed++;
    }
    if (Simulator::Now().GetSeconds() + interval < stop - 1e-9)
    {
        Simulator::Schedule(Seconds(interval), &SendPacket, f, stop, interval);
    }
}

void
ReceivePacket(uint32_t f, Ptr<Socket> socket)
{
    Address from;
    while (Ptr<Packet> packet = socket->RecvFrom(from))
    {
        SeqTsHeader header;
        packet->RemoveHeader(header);
        uint32_t seq = header.GetSeq();
        if (seq < g_flows[f].packets.size() && g_flows[f].packets[seq].rx < 0)
        {
            g_flows[f].packets[seq].rx = Simulator::Now().GetSeconds();
        }
        else
        {
            g_duplicates++;
        }
    }
}

void
OnForward(uint32_t node, const Ipv4Header& header, Ptr<const Packet> payload, uint32_t)
{
    uint32_t f;
    uint32_t seq;
    if (header.GetProtocol() == UdpL4Protocol::PROT_NUMBER && header.GetFragmentOffset() == 0 &&
        ParseData(payload, f, seq))
    {
        g_flows[f].packets[seq].path.push_back(node);
    }
}

// Drop codes: 1 = source had no route (SendTo refused); 10 + Ipv4L3Protocol::DropReason;
// 20 + WifiMacDropReason. experiments/metrics.py turns them into names.
void
OnIpDrop(uint32_t node,
         const Ipv4Header& header,
         Ptr<const Packet> packet,
         Ipv4L3Protocol::DropReason reason,
         Ptr<Ipv4>,
         uint32_t)
{
    if (header.GetProtocol() != UdpL4Protocol::PROT_NUMBER || header.GetFragmentOffset() != 0)
    {
        return;
    }
    Ptr<const Packet> payload = packet;
    uint8_t first = 0;
    if (packet->GetSize() > 0 && packet->CopyData(&first, 1) == 1 && first == 0x45)
    {
        Ptr<Packet> copy = packet->Copy(); // some drop paths still carry the IP header
        Ipv4Header ip;
        copy->RemoveHeader(ip);
        payload = copy;
    }
    uint32_t f;
    uint32_t seq;
    if (ParseData(payload, f, seq))
    {
        RecordDrop(f, seq, 10 + static_cast<int>(reason), node);
    }
}

void
OnMacDrop(uint32_t node, WifiMacDropReason reason, Ptr<const WifiMpdu> mpdu)
{
    const WifiMacHeader& hdr = mpdu->GetHeader();
    if (!hdr.IsData())
    {
        return;
    }
    if (reason == WIFI_MAC_DROP_REACHED_RETRY_LIMIT && !hdr.GetAddr1().IsGroup())
    {
        g_macRetryDrops[Bin()]++;
    }
    Ptr<Packet> copy = mpdu->GetPacket()->Copy();
    LlcSnapHeader llc;
    if (copy->GetSize() < llc.GetSerializedSize())
    {
        return;
    }
    copy->RemoveHeader(llc);
    if (llc.GetType() != Ipv4L3Protocol::PROT_NUMBER)
    {
        return;
    }
    Ipv4Header ip;
    copy->RemoveHeader(ip);
    uint32_t f;
    uint32_t seq;
    if (ip.GetProtocol() == UdpL4Protocol::PROT_NUMBER && ip.GetFragmentOffset() == 0 &&
        ParseData(copy, f, seq))
    {
        RecordDrop(f, seq, 20 + static_cast<int>(reason), node);
    }
}

// ---------------------------------------------------------------------------
// Routing control traffic
// ---------------------------------------------------------------------------

// Counts every routing packet a working node hands to its interface, including
// rebroadcasts. Bytes are IP-layer bytes (IP + UDP headers + routing message). A packet
// sent as IP fragments counts once, with the bytes of all its fragments.
void
OnIpTx(uint32_t node, Ptr<const Packet> packet, Ptr<Ipv4>, uint32_t)
{
    if (!g_alive[node])
    {
        return; // a dead radio transmits nothing
    }
    Ptr<Packet> copy = packet->Copy();
    Ipv4Header ip;
    copy->RemoveHeader(ip);
    if (ip.GetProtocol() != UdpL4Protocol::PROT_NUMBER)
    {
        return;
    }
    uint32_t ipBytes = packet->GetSize();
    if (ip.GetFragmentOffset() != 0 || !ip.IsLastFragment())
    {
        // Fragments of one packet are traced back to back, in order, so join them here.
        if (ip.GetFragmentOffset() == 0)
        {
            g_txFragments[node] = copy;
            g_txFragmentBytes[node] = ipBytes;
            g_txFragmentId[node] = ip.GetIdentification();
            return;
        }
        auto it = g_txFragments.find(node);
        if (it == g_txFragments.end() || g_txFragmentId[node] != ip.GetIdentification())
        {
            return;
        }
        it->second->AddAtEnd(copy);
        g_txFragmentBytes[node] += ipBytes;
        if (!ip.IsLastFragment())
        {
            return;
        }
        copy = it->second;
        ipBytes = g_txFragmentBytes[node];
        g_txFragments.erase(it);
        UdpHeader peek;
        copy->PeekHeader(peek);
        if (peek.GetDestinationPort() == g_routingPort)
        {
            g_fragmentedRoutingPackets++;
        }
    }
    UdpHeader udp;
    copy->RemoveHeader(udp);
    if (udp.GetDestinationPort() != g_routingPort)
    {
        return;
    }
    uint32_t bin = Bin();
    g_ctrlPkts[bin]++;
    g_ctrlBytes[bin] += ipBytes;

    if (g_protocol == "aodv")
    {
        aodv::TypeHeader type;
        copy->RemoveHeader(type);
        if (!type.IsValid())
        {
            return;
        }
        switch (type.Get())
        {
        case aodv::AODVTYPE_RREQ: {
            aodv::RreqHeader rreq;
            copy->RemoveHeader(rreq);
            if (NodeOfAddress(rreq.GetOrigin()) == static_cast<int>(node))
            {
                g_ctrlTypes[bin][0]++;
                int dst = NodeOfAddress(rreq.GetDst());
                auto key = std::make_pair(node, static_cast<uint32_t>(dst));
                auto it = g_pendingDiscovery.find(key);
                if (it != g_pendingDiscovery.end())
                {
                    g_discoveries[it->second].attempts++;
                }
                else
                {
                    Discovery d;
                    d.origin = node;
                    d.dst = dst;
                    d.start = Simulator::Now().GetSeconds();
                    g_pendingDiscovery[key] = g_discoveries.size();
                    g_discoveries.push_back(d);
                }
            }
            else
            {
                g_ctrlTypes[bin][1]++;
            }
            break;
        }
        case aodv::AODVTYPE_RREP: {
            aodv::RrepHeader rrep;
            copy->RemoveHeader(rrep);
            g_ctrlTypes[bin][rrep.GetDst() == rrep.GetOrigin() ? 4 : 2]++;
            break;
        }
        case aodv::AODVTYPE_RERR:
            g_ctrlTypes[bin][3]++;
            break;
        case aodv::AODVTYPE_RREP_ACK:
            g_ctrlTypes[bin][5]++;
            break;
        }
    }
    else if (g_protocol == "olsr")
    {
        olsr::PacketHeader ph;
        copy->RemoveHeader(ph);
        while (copy->GetSize() > 0)
        {
            olsr::MessageHeader mh;
            if (copy->RemoveHeader(mh) == 0)
            {
                break;
            }
            int t = static_cast<int>(mh.GetMessageType()) - 1;
            if (t >= 0 && t < 4)
            {
                g_ctrlTypes[bin][t]++;
            }
        }
    }
}

// AODV: a route discovery ends when a RREP for it reaches the node that sent the RREQ.
void
OnIpRx(uint32_t node, Ptr<const Packet> packet, Ptr<Ipv4>, uint32_t)
{
    Ptr<Packet> copy = packet->Copy();
    Ipv4Header ip;
    copy->RemoveHeader(ip);
    if (ip.GetProtocol() != UdpL4Protocol::PROT_NUMBER || ip.GetFragmentOffset() != 0)
    {
        return;
    }
    UdpHeader udp;
    copy->RemoveHeader(udp);
    if (udp.GetDestinationPort() != AODV_PORT)
    {
        return;
    }
    aodv::TypeHeader type;
    copy->RemoveHeader(type);
    if (!type.IsValid() || type.Get() != aodv::AODVTYPE_RREP)
    {
        return;
    }
    aodv::RrepHeader rrep;
    copy->RemoveHeader(rrep);
    if (rrep.GetDst() == rrep.GetOrigin() || NodeOfAddress(rrep.GetOrigin()) != static_cast<int>(node))
    {
        return;
    }
    auto key = std::make_pair(node, static_cast<uint32_t>(NodeOfAddress(rrep.GetDst())));
    auto it = g_pendingDiscovery.find(key);
    if (it != g_pendingDiscovery.end())
    {
        g_discoveries[it->second].end = Simulator::Now().GetSeconds();
        g_pendingDiscovery.erase(it);
    }
}

// ---------------------------------------------------------------------------
// Failures
// ---------------------------------------------------------------------------
void
LogEvent(const std::string& action, const std::string& kind, int a, int b, const std::string& group)
{
    g_eventLog.push_back({Simulator::Now().GetSeconds(), action, kind, a, b, group});
}

// Switches a radio off: no send, receive or ACK, like a dead device. A radio in the
// middle of sending a frame finishes it first (a few ms at most): ns-3.47 crashes if a
// radio is switched off while sending a frame that needs no acknowledgement, because
// FrameExchangeManager::TransmissionSucceeded then runs after Reset() cleared m_dcf.
void
SwitchOff(uint32_t node)
{
    Ptr<WifiPhy> phy = PhyOf(node);
    if (phy->IsStateTx())
    {
        Simulator::Schedule(MicroSeconds(100), &SwitchOff, node);
        return;
    }
    if (!phy->IsStateOff())
    {
        phy->SetOffMode();
    }
}

void
ApplyEvent(FailureEvent e)
{
    if (e.kind == "node")
    {
        if (e.action == "fail" && g_alive[e.a])
        {
            SwitchOff(e.a);
            g_alive[e.a] = false;
            LogEvent("fail", "node", e.a, -1, e.group);
        }
        else if (e.action == "restore" && !g_alive[e.a] && !g_depleted[e.a] && PhyOf(e.a)->IsStateOff())
        {
            PhyOf(e.a)->ResumeFromOff();
            g_alive[e.a] = true;
            LogEvent("restore", "node", e.a, -1, e.group);
        }
    }
    else if (e.kind == "link")
    {
        auto key = LinkKey(e.a, e.b);
        if (e.action == "fail")
        {
            g_blocked.insert(key);
        }
        else
        {
            g_blocked.erase(key);
        }
        LogEvent(e.action, "link", e.a, e.b, e.group);
    }
}

void
OnDepleted(uint32_t node)
{
    g_depletionTime[node] = Simulator::Now().GetSeconds();
    g_depleted[node] = true;
    if (g_alive[node])
    {
        SwitchOff(node);
        g_alive[node] = false;
    }
    LogEvent("deplete", "node", node, -1, "battery");
}

void
OnRecharged()
{
    // Batteries are never recharged in these scenarios (no mains power).
}

void
OnPhyState(uint32_t node, Time start, Time duration, WifiPhyState state)
{
    g_stateTime[node][static_cast<int>(state)] += duration.GetSeconds();
    g_lastStateChange[node] = (start + duration).GetSeconds();
}

// Energy used so far, including the state the radio is in right now.
double
ConsumedJ(uint32_t node)
{
    double j = 0;
    for (int st = 0; st < 7; st++)
    {
        j += g_stateTime[node][st] * STATE_CURRENT_A[st];
    }
    auto now = static_cast<int>(PhyOf(node)->GetState()->GetState());
    j += (Simulator::Now().GetSeconds() - g_lastStateChange[node]) * STATE_CURRENT_A[now];
    return j * SUPPLY_V;
}

// Once a second, like BasicEnergySource's periodic update.
void
BatteryCheck()
{
    for (uint32_t i = 0; i < g_n; i++)
    {
        if (g_initialJ[i] > 0 && !g_depleted[i] &&
            g_initialJ[i] - ConsumedJ(i) <= LOW_BATTERY_FRACTION * g_initialJ[i])
        {
            OnDepleted(i);
        }
    }
    Simulator::Schedule(Seconds(1), &BatteryCheck);
}

// ---------------------------------------------------------------------------
// Route validity (OLSR and DSDV)
// ---------------------------------------------------------------------------

// Next hop of every node towards every destination, from the protocol's own table.
std::vector<std::vector<int>>
NextHops()
{
    std::vector<std::vector<int>> next(g_n, std::vector<int>(g_n, -1));
    for (uint32_t i = 0; i < g_n; i++)
    {
        if (!g_alive[i])
        {
            continue;
        }
        if (g_protocol == "olsr")
        {
            for (const auto& e : g_olsr[i]->GetRoutingTableEntries())
            {
                int d = NodeOfAddress(e.destAddr);
                int h = NodeOfAddress(e.nextAddr);
                if (d >= 0 && h >= 0)
                {
                    next[i][d] = h;
                }
            }
        }
        else
        {
            std::ostringstream oss;
            Ptr<OutputStreamWrapper> stream = Create<OutputStreamWrapper>(&oss);
            g_routing[i]->PrintRoutingTable(stream, Time::S);
            std::istringstream lines(oss.str());
            std::string line;
            while (std::getline(lines, line))
            {
                std::istringstream cells(line);
                std::string dst;
                std::string gw;
                if (!(cells >> dst >> gw))
                {
                    continue;
                }
                if (dst.empty() || !std::isdigit(static_cast<unsigned char>(dst[0])))
                {
                    continue;
                }
                int d = NodeOfAddress(Ipv4Address(dst.c_str()));
                int h = NodeOfAddress(Ipv4Address(gw.c_str()));
                if (d >= 0 && h >= 0 && d != static_cast<int>(i))
                {
                    next[i][d] = h;
                }
            }
        }
    }
    return next;
}

// Every second: of the node pairs that are connected right now, how many have
// routing-table entries that actually lead to the destination over working links?
void
SampleRoutes()
{
    // Connected components of the current network.
    std::vector<int> comp(g_n, -1);
    int nComp = 0;
    for (uint32_t s = 0; s < g_n; s++)
    {
        if (!g_alive[s] || comp[s] >= 0)
        {
            continue;
        }
        std::queue<uint32_t> q;
        q.push(s);
        comp[s] = nComp;
        while (!q.empty())
        {
            uint32_t u = q.front();
            q.pop();
            for (uint32_t v = 0; v < g_n; v++)
            {
                if (comp[v] < 0 && v != u && LinkUp(u, v))
                {
                    comp[v] = nComp;
                    q.push(v);
                }
            }
        }
        nComp++;
    }

    auto next = NextHops();
    uint64_t reachable = 0;
    uint64_t valid = 0;
    uint32_t aliveCount = 0;
    for (uint32_t s = 0; s < g_n; s++)
    {
        if (!g_alive[s])
        {
            continue;
        }
        aliveCount++;
        for (uint32_t d = 0; d < g_n; d++)
        {
            if (d == s || !g_alive[d] || comp[d] != comp[s])
            {
                continue;
            }
            reachable++;
            uint32_t cur = s;
            bool ok = false;
            for (uint32_t steps = 0; steps < g_n; steps++)
            {
                int h = next[cur][d];
                if (h < 0 || !LinkUp(cur, h))
                {
                    break;
                }
                cur = h;
                if (cur == d)
                {
                    ok = true;
                    break;
                }
            }
            valid += ok;
        }
    }
    g_routesOut << Simulator::Now().GetSeconds() << "," << aliveCount << "," << nComp << ","
                << reachable << "," << valid << "\n";
    if (Simulator::Now().GetSeconds() + g_sampleInterval < g_simTime)
    {
        Simulator::Schedule(Seconds(g_sampleInterval), &SampleRoutes);
    }
}

} // namespace

int
main(int argc, char* argv[])
{
    auto wallStart = std::chrono::steady_clock::now();

    std::string topoFile;
    std::string flowsFile;
    std::string eventsFile;
    std::string outDir = ".";
    uint32_t run = 1;
    double energyJ = 0;
    bool flowmon = false;
    std::string rtDump;
    std::string energyFile;
    std::string energyModel = "states";
    bool rtsCts = false;
    double idleCurrentA = STATE_CURRENT_A[0];
    double txPowerDbm = 16.0206; // ns-3 WifiPhy default
    std::string lossModel = "range";
    double logExponent = 3.0;   // ns-3 LogDistancePropagationLossModel default
    double logRefLoss = 46.6777; // ns-3 default: Friis loss at 1 m and 5.15 GHz

    CommandLine cmd(__FILE__);
    cmd.AddValue("protocol", "Routing protocol: aodv, olsr or dsdv", g_protocol);
    cmd.AddValue("topo", "Topology CSV: node_id,x,y", topoFile);
    cmd.AddValue("flows", "Traffic CSV: flow_id,src,dst,start_s,stop_s,interval_s,payload_bytes", flowsFile);
    cmd.AddValue("events", "Failure schedule CSV: time_s,action,kind,a,b,group (optional)", eventsFile);
    cmd.AddValue("outDir", "Folder for the outputs (must exist)", outDir);
    cmd.AddValue("run", "Run number for the random stream (ns-3 RngRun)", run);
    cmd.AddValue("simTime", "Simulation length (s)", g_simTime);
    cmd.AddValue("range", "Radio range (m): RangePropagationLossModel MaxRange", g_range);
    cmd.AddValue("txPower", "Transmit power (dBm)", txPowerDbm);
    cmd.AddValue("lossModel",
                 "range (unit disk, default) or logdistance (then --range is only the link distance "
                 "the connectivity metrics use)",
                 lossModel);
    cmd.AddValue("logExponent", "Path-loss exponent for --lossModel=logdistance", logExponent);
    cmd.AddValue("logRefLoss", "Path loss (dB) at 1 m for --lossModel=logdistance", logRefLoss);
    cmd.AddValue("energyJ", "Initial battery energy per node (J); 0 = unlimited (energy still measured)", energyJ);
    cmd.AddValue("rtsCts", "Use RTS/CTS for every unicast frame (default: off, as in ns-3)", rtsCts);
    cmd.AddValue("energyModel", "states (fast, default) or ns3 (also run BasicEnergySource + WifiRadioEnergyModel)", energyModel);
    cmd.AddValue("idleCurrentA", "Idle and CCA-busy current (A) for --energyModel=states (default 0.273)", idleCurrentA);
    cmd.AddValue("energyFile", "Per-node initial energy CSV: node,initial_J (overrides --energyJ)", energyFile);
    cmd.AddValue("sampleInterval", "Route-validity sampling interval (s); 0 = off", g_sampleInterval);
    cmd.AddValue("flowmon", "Also write FlowMonitor XML", flowmon);
    cmd.AddValue("rtDump", "Comma-separated times (s) at which to dump all routing tables", rtDump);
    cmd.Parse(argc, argv);

    if (g_protocol != "aodv" && g_protocol != "olsr" && g_protocol != "dsdv")
    {
        NS_FATAL_ERROR("--protocol must be aodv, olsr or dsdv");
    }
    if (lossModel != "range" && lossModel != "logdistance")
    {
        NS_FATAL_ERROR("--lossModel must be range or logdistance");
    }
    STATE_CURRENT_A[0] = idleCurrentA;
    STATE_CURRENT_A[1] = idleCurrentA;
    if (energyModel == "ns3" && idleCurrentA != 0.273)
    {
        NS_FATAL_ERROR("--idleCurrentA only applies to --energyModel=states");
    }
    g_routingPort = g_protocol == "aodv" ? AODV_PORT : (g_protocol == "olsr" ? OLSR_PORT : DSDV_PORT);

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(run);

    // ---- Nodes and positions ----
    auto topo = ReadCsv(topoFile);
    g_n = topo.size();
    g_nodes.Create(g_n);
    Ptr<ListPositionAllocator> positions = CreateObject<ListPositionAllocator>();
    for (const auto& row : topo)
    {
        Vector p(std::stod(row[1]), std::stod(row[2]), 0);
        g_pos.push_back(p);
        positions->Add(p);
    }
    MobilityHelper mobility;
    mobility.SetPositionAllocator(positions);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(g_nodes);
    g_alive.assign(g_n, true);
    g_depleted.assign(g_n, false);
    g_depletionTime.assign(g_n, -1);

    // ---- Radio: ad-hoc 802.11b, unit-disk range, failed links silenced ----
    // With --lossModel=logdistance, received power falls with distance instead, and the
    // ns-3 PHY defaults (preamble detection, error model) decide which frames get through.
    Ptr<YansWifiChannel> channel = CreateObject<YansWifiChannel>();
    Ptr<PropagationLossModel> distanceLoss;
    if (lossModel == "range")
    {
        distanceLoss = CreateObject<RangePropagationLossModel>();
        distanceLoss->SetAttribute("MaxRange", DoubleValue(g_range));
    }
    else
    {
        distanceLoss = CreateObject<LogDistancePropagationLossModel>();
        distanceLoss->SetAttribute("Exponent", DoubleValue(logExponent));
        distanceLoss->SetAttribute("ReferenceDistance", DoubleValue(1.0));
        distanceLoss->SetAttribute("ReferenceLoss", DoubleValue(logRefLoss));
    }
    distanceLoss->SetNext(CreateObject<LinkBlockLossModel>());
    channel->SetPropagationLossModel(distanceLoss);
    channel->SetPropagationDelayModel(CreateObject<ConstantSpeedPropagationDelayModel>());
    YansWifiPhyHelper phy;
    phy.SetChannel(channel);
    phy.Set("TxPowerStart", DoubleValue(txPowerDbm));
    phy.Set("TxPowerEnd", DoubleValue(txPowerDbm));
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211b);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",
                                 StringValue("DsssRate11Mbps"),
                                 "ControlMode",
                                 StringValue("DsssRate1Mbps"));
    if (rtsCts)
    {
        // RTS/CTS before every unicast frame (ns-3 default: off), to test how much
        // hidden-terminal collisions matter.
        wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                     "DataMode",
                                     StringValue("DsssRate11Mbps"),
                                     "ControlMode",
                                     StringValue("DsssRate1Mbps"),
                                     "RtsCtsThreshold",
                                     UintegerValue(0));
    }
    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");
    g_devices = wifi.Install(phy, mac, g_nodes);

    // ---- Routing ----
    InternetStackHelper internet;
    AodvHelper aodv;
    OlsrHelper olsr;
    DsdvHelper dsdv;
    Ipv4ListRoutingHelper list;
    if (g_protocol == "aodv")
    {
        internet.SetRoutingHelper(aodv);
    }
    else if (g_protocol == "olsr")
    {
        list.Add(olsr, 100);
        internet.SetRoutingHelper(list);
    }
    else
    {
        internet.SetRoutingHelper(dsdv);
    }
    internet.Install(g_nodes);
    Ipv4AddressHelper addresses;
    addresses.SetBase("10.1.0.0", "255.255.0.0");
    g_ifaces = addresses.Assign(g_devices);
    for (uint32_t i = 0; i < g_n; i++)
    {
        g_addrToNode[g_ifaces.GetAddress(i).Get()] = i;
    }

    // Static ARP: every node knows every other node's MAC address from the start,
    // so there is no ARP traffic. The entries are marked PERMANENT rather than made
    // with NeighborCacheHelper, because AODV's link-break detection
    // (aodv::Neighbors::LookupMacAddress) ignores NeighborCacheHelper's
    // STATIC_AUTOGENERATED entries and would then never notice a dead next hop.
    for (uint32_t i = 0; i < g_n; i++)
    {
        Ptr<Ipv4L3Protocol> l3 = g_nodes.Get(i)->GetObject<Ipv4L3Protocol>();
        Ptr<ArpCache> cache = l3->GetInterface(1)->GetArpCache();
        for (uint32_t j = 0; j < g_n; j++)
        {
            if (j != i)
            {
                ArpCache::Entry* entry = cache->Add(g_ifaces.GetAddress(j));
                entry->SetMacAddress(g_devices.Get(j)->GetAddress());
                entry->MarkPermanent();
            }
        }
    }

    for (uint32_t i = 0; i < g_n; i++)
    {
        Ptr<Ipv4> ipv4 = g_nodes.Get(i)->GetObject<Ipv4>();
        g_routing.push_back(ipv4->GetRoutingProtocol());
        if (g_protocol == "olsr")
        {
            int16_t priority;
            Ptr<Ipv4ListRouting> lr = DynamicCast<Ipv4ListRouting>(ipv4->GetRoutingProtocol());
            g_olsr.push_back(DynamicCast<olsr::RoutingProtocol>(lr->GetRoutingProtocol(0, priority)));
        }
    }

    // ---- Energy ----
    g_initialJ.assign(g_n, energyJ);
    if (!energyFile.empty())
    {
        for (const auto& row : ReadCsv(energyFile))
        {
            g_initialJ.at(std::stoul(row[0])) = std::stod(row[1]);
        }
    }
    g_stateTime.assign(g_n, {});
    g_lastStateChange.assign(g_n, 0.0);
    for (uint32_t i = 0; i < g_n; i++)
    {
        PhyOf(i)->GetState()->TraceConnectWithoutContext("State", MakeBoundCallback(&OnPhyState, i));
    }
    bool batteries = *std::max_element(g_initialJ.begin(), g_initialJ.end()) > 0;
    if (energyModel == "ns3")
    {
        for (uint32_t i = 0; i < g_n; i++)
        {
            BasicEnergySourceHelper sourceHelper;
            double j = g_initialJ[i] > 0 ? g_initialJ[i] : 1e9; // effectively unlimited
            sourceHelper.Set("BasicEnergySourceInitialEnergyJ", DoubleValue(j));
            energy::EnergySourceContainer src = sourceHelper.Install(g_nodes.Get(i));
            WifiRadioEnergyModelHelper radioHelper;
            radioHelper.SetDepletionCallback(MakeBoundCallback(&OnDepleted, i));
            radioHelper.SetRechargedCallback(MakeCallback(&OnRecharged));
            energy::DeviceEnergyModelContainer models = radioHelper.Install(g_devices.Get(i), src.Get(0));
            g_sources.push_back(src.Get(0));
            g_radioModels.push_back(models.Get(0));
        }
    }
    else if (batteries)
    {
        Simulator::Schedule(Seconds(1), &BatteryCheck);
    }

    // ---- Traffic ----
    auto flowRows = ReadCsv(flowsFile);
    uint32_t nFlows = 0;
    for (const auto& row : flowRows)
    {
        nFlows = std::max<uint32_t>(nFlows, std::stoul(row[0]) + 1);
    }
    g_flows.resize(nFlows);
    std::vector<Segment> segments;
    for (const auto& row : flowRows)
    {
        uint32_t f = std::stoul(row[0]);
        g_flows[f].src = std::stoul(row[1]);
        g_flows[f].dst = std::stoul(row[2]);
        g_flows[f].payload = std::stoul(row[6]);
        segments.push_back({f, std::stod(row[3]), std::stod(row[4]), std::stod(row[5])});
    }
    for (uint32_t f = 0; f < nFlows; f++)
    {
        Flow& flow = g_flows[f];
        Ptr<Socket> rx = Socket::CreateSocket(g_nodes.Get(flow.dst), UdpSocketFactory::GetTypeId());
        rx->Bind(InetSocketAddress(Ipv4Address::GetAny(), PORT_BASE + f));
        rx->SetRecvCallback(MakeBoundCallback(&ReceivePacket, f));
        flow.tx = Socket::CreateSocket(g_nodes.Get(flow.src), UdpSocketFactory::GetTypeId());
    }
    for (const auto& s : segments)
    {
        Simulator::Schedule(Seconds(s.start), &SendPacket, s.flow, s.stop, s.interval);
    }

    // ---- Failure schedule ----
    if (!eventsFile.empty())
    {
        for (const auto& row : ReadCsv(eventsFile))
        {
            FailureEvent e{std::stod(row[0]), row[1], row[2], std::stoi(row[3]), std::stoi(row[4]), row.size() > 5 ? row[5] : ""};
            Simulator::Schedule(Seconds(e.time), &ApplyEvent, e);
        }
    }

    // ---- Tracing ----
    uint32_t nBins = static_cast<uint32_t>(std::ceil(g_simTime)) + 1;
    g_ctrlPkts.assign(nBins, 0);
    g_ctrlBytes.assign(nBins, 0);
    g_ctrlTypes.assign(nBins, {});
    g_macRetryDrops.assign(nBins, 0);
    for (uint32_t i = 0; i < g_n; i++)
    {
        Ptr<Ipv4L3Protocol> l3 = g_nodes.Get(i)->GetObject<Ipv4L3Protocol>();
        l3->TraceConnectWithoutContext("Tx", MakeBoundCallback(&OnIpTx, i));
        l3->TraceConnectWithoutContext("UnicastForward", MakeBoundCallback(&OnForward, i));
        l3->TraceConnectWithoutContext("Drop", MakeBoundCallback(&OnIpDrop, i));
        if (g_protocol == "aodv")
        {
            l3->TraceConnectWithoutContext("Rx", MakeBoundCallback(&OnIpRx, i));
        }
        Ptr<WifiMac> wifiMac = DynamicCast<WifiNetDevice>(g_devices.Get(i))->GetMac();
        wifiMac->TraceConnectWithoutContext("DroppedMpdu", MakeBoundCallback(&OnMacDrop, i));
    }

    if (g_protocol != "aodv" && g_sampleInterval > 0)
    {
        g_routesOut.open(outDir + "/routes.csv");
        g_routesOut << "t_s,alive_nodes,components,reachable_pairs,valid_pairs\n";
        Simulator::Schedule(Seconds(g_sampleInterval), &SampleRoutes);
    }

    if (!rtDump.empty())
    {
        std::stringstream ss(rtDump);
        std::string t;
        while (std::getline(ss, t, ','))
        {
            auto stream = Create<OutputStreamWrapper>(outDir + "/rtables-" + t + "s.txt", std::ios::out);
            Ipv4RoutingHelper::PrintRoutingTableAllAt(Seconds(std::stod(t)), stream);
        }
    }

    FlowMonitorHelper flowmonHelper;
    Ptr<FlowMonitor> monitor;
    if (flowmon)
    {
        monitor = flowmonHelper.InstallAll();
    }

    Simulator::Stop(Seconds(g_simTime));
    Simulator::Run();

    // ---- Outputs ----
    std::ofstream packets(outDir + "/packets.csv");
    packets << "flow,seq,tx_s,rx_s,path,drop_code,drop_node,drop_s\n";
    packets << std::fixed << std::setprecision(6);
    for (uint32_t f = 0; f < g_flows.size(); f++)
    {
        const auto& recs = g_flows[f].packets;
        for (uint32_t s = 0; s < recs.size(); s++)
        {
            const auto& r = recs[s];
            packets << f << "," << s << "," << r.tx << ",";
            if (r.rx >= 0)
            {
                packets << r.rx;
            }
            packets << ",";
            for (size_t k = 0; k < r.path.size(); k++)
            {
                packets << (k ? "-" : "") << r.path[k];
            }
            packets << "," << r.dropCode << "," << r.dropNode << ",";
            if (r.dropTime >= 0)
            {
                packets << r.dropTime;
            }
            packets << "\n";
        }
    }
    packets.close();

    std::ofstream control(outDir + "/control.csv");
    control << "t_s,pkts,bytes,type0,type1,type2,type3,type4,type5,mac_retry_drops\n";
    for (uint32_t b = 0; b < nBins - 1; b++)
    {
        control << b << "," << g_ctrlPkts[b] << "," << g_ctrlBytes[b];
        for (int t = 0; t < N_TYPES; t++)
        {
            control << "," << g_ctrlTypes[b][t];
        }
        control << "," << g_macRetryDrops[b] << "\n";
    }
    control.close();

    std::ofstream events(outDir + "/events.csv");
    events << "time_s,action,kind,a,b,group\n";
    for (const auto& e : g_eventLog)
    {
        events << e.time << "," << e.action << "," << e.kind << "," << e.a << "," << e.b << ","
               << e.group << "\n";
    }
    events.close();

    std::ofstream en(outDir + "/energy.csv");
    en << "node,initial_J,consumed_J,consumed_ns3_J,remaining_J,depleted_s,t_idle_s,t_cca_busy_s,t_tx_s,t_rx_s,t_off_s\n";
    for (uint32_t i = 0; i < g_n; i++)
    {
        double used = ConsumedJ(i);
        en << i << ",";
        if (g_initialJ[i] > 0)
        {
            en << g_initialJ[i];
        }
        en << "," << used << ",";
        if (!g_radioModels.empty())
        {
            en << g_radioModels[i]->GetTotalEnergyConsumption();
        }
        en << ",";
        if (g_initialJ[i] > 0)
        {
            en << std::max(0.0, g_initialJ[i] - used);
        }
        en << ",";
        if (g_depletionTime[i] >= 0)
        {
            en << g_depletionTime[i];
        }
        en << "," << g_stateTime[i][0] << "," << g_stateTime[i][1] << "," << g_stateTime[i][2] << ","
           << g_stateTime[i][3] << "," << g_stateTime[i][6] << "\n";
    }
    en.close();

    if (g_protocol == "aodv")
    {
        std::ofstream disc(outDir + "/discoveries.csv");
        disc << "origin,dst,start_s,end_s,attempts\n";
        for (const auto& d : g_discoveries)
        {
            disc << d.origin << "," << d.dst << "," << d.start << ",";
            if (d.end >= 0)
            {
                disc << d.end;
            }
            disc << "," << d.attempts << "\n";
        }
    }

    if (flowmon)
    {
        monitor->CheckForLostPackets();
        monitor->SerializeToXmlFile(outDir + "/flowmon.xml", false, false);
    }

    double wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - wallStart).count();
    std::ofstream stats(outDir + "/stats.csv");
    stats << "protocol,nodes,flows,suppressed_sends,socket_errors,duplicate_receptions,wall_s\n";
    stats << g_protocol << "," << g_n << "," << g_flows.size() << "," << g_suppressed << ","
          << g_socketErrors << "," << g_duplicates << "," << wall << "\n";
    stats.close();

    std::cout << "done protocol=" << g_protocol << " nodes=" << g_n << " flows=" << g_flows.size()
              << " wall_s=" << wall << " fragmented_routing_packets=" << g_fragmentedRoutingPackets
              << std::endl;

    Simulator::Destroy();
    return 0;
}
