// Diamond sanity simulation.
//
// Node A sends a steady UDP stream to node C. There are two equal two-hop paths,
// A-B-C and A-D-C, and A can't reach C directly:
//
//            B (80, 60)
//          /           \
//   A (0, 0)            C (160, 0)
//          \           /
//            D (80, -60)
//
// Every link is 100 m and the radio range is 110 m, so A-C (160 m) and B-D (120 m)
// are out of range. At --killTime the relay A is currently using is switched off
// (radio off, like a dead battery). The run records how the routing protocol recovers.
//
// Usage, from the repo root:
//   scripts/run.sh diamond --protocol=aodv --run=1
//   scripts/run.sh diamond --protocol=olsr --run=1
//
// Outputs (in --outDir):
//   diamond-<protocol>-run<N>.csv   one row per packet sent
//   diamond-summary.csv             one row per run, appended

#include "ns3/aodv-module.h"
#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/olsr-module.h"
#include "ns3/wifi-module.h"

#include <fstream>
#include <map>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("Diamond");

namespace
{

enum NodeIndex : uint32_t
{
    A = 0,
    B = 1,
    C = 2,
    D = 3
};

const char* NODE_NAME[] = {"A", "B", "C", "D"};
const uint16_t DATA_PORT = 9;

// Filled in by main() before the simulation starts.
NodeContainer g_nodes;
NetDeviceContainer g_devices;
Ipv4InterfaceContainer g_ifaces;
Ptr<Socket> g_txSocket;
Address g_dest;
uint32_t g_payloadBytes = 64;
Time g_interval;
Time g_stopSending;
uint16_t g_routingPort = 0;

// Filled in while the simulation runs.
uint32_t g_seq = 0;
uint32_t g_sendErrors = 0;
uint64_t g_controlPackets = 0;
uint32_t g_victim = B;
std::map<uint32_t, double> g_txTime; // seq -> send time (s)
std::map<uint32_t, double> g_rxTime; // seq -> first receive time (s)

// A sends one numbered, timestamped packet, then schedules the next one.
void
SendPacket()
{
    SeqTsHeader header; // stamps the current time
    header.SetSeq(g_seq);
    Ptr<Packet> packet = Create<Packet>(g_payloadBytes);
    packet->AddHeader(header);
    g_txTime[g_seq] = Simulator::Now().GetSeconds();
    if (g_txSocket->SendTo(packet, 0, g_dest) < 0)
    {
        g_sendErrors++; // no route at send time; counted as sent but never delivered
    }
    g_seq++;
    if (Simulator::Now() + g_interval < g_stopSending)
    {
        Simulator::Schedule(g_interval, &SendPacket);
    }
}

// C records the first arrival of each sequence number.
void
ReceivePacket(Ptr<Socket> socket)
{
    Address from;
    while (Ptr<Packet> packet = socket->RecvFrom(from))
    {
        SeqTsHeader header;
        packet->RemoveHeader(header);
        g_rxTime.emplace(header.GetSeq(), Simulator::Now().GetSeconds());
    }
}

// Counts routing control packets (AODV or OLSR) sent at the IP layer by any node,
// including rebroadcasts. Data packets use a different port and aren't counted.
void
IpTx(Ptr<const Packet> packet, Ptr<Ipv4>, uint32_t)
{
    Ptr<Packet> copy = packet->Copy();
    Ipv4Header ip;
    copy->RemoveHeader(ip);
    if (ip.GetProtocol() != UdpL4Protocol::PROT_NUMBER)
    {
        return;
    }
    UdpHeader udp;
    copy->PeekHeader(udp);
    if (udp.GetDestinationPort() == g_routingPort)
    {
        g_controlPackets++;
    }
}

// Asks A's routing protocol which neighbour it would use to reach C right now.
uint32_t
CurrentRelay()
{
    Ptr<Ipv4> ipv4 = g_nodes.Get(A)->GetObject<Ipv4>();
    Ipv4Header header;
    header.SetSource(g_ifaces.GetAddress(A));
    header.SetDestination(g_ifaces.GetAddress(C));
    header.SetProtocol(UdpL4Protocol::PROT_NUMBER);
    Socket::SocketErrno err;
    Ptr<Ipv4Route> route =
        ipv4->GetRoutingProtocol()->RouteOutput(Create<Packet>(), header, nullptr, err);
    if (route && route->GetGateway() == g_ifaces.GetAddress(B))
    {
        return B;
    }
    if (route && route->GetGateway() == g_ifaces.GetAddress(D))
    {
        return D;
    }
    return C; // no usable route through either relay
}

// Switches a node's radio off: it stops sending, receiving and acknowledging frames.
void
KillNode(std::string mode)
{
    if (mode == "relay")
    {
        uint32_t relay = CurrentRelay();
        if (relay == C)
        {
            NS_LOG_UNCOND("Warning: A had no route through B or D at the kill time; killing B");
            relay = B;
        }
        g_victim = relay;
    }
    else
    {
        g_victim = (mode == "D") ? D : B;
    }
    NS_LOG_UNCOND("t=" << Simulator::Now().GetSeconds() << "s: switching off node "
                       << NODE_NAME[g_victim]);
    DynamicCast<WifiNetDevice>(g_devices.Get(g_victim))->GetPhy()->SetOffMode();
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string protocol = "aodv";
    uint32_t run = 1;
    double simTime = 60.0;
    double trafficStart = 15.0;
    double killTime = 30.0;
    double interval = 0.1;
    double deadline = 1.0;
    double window = 10.0;
    double range = 110.0;
    bool aodvHello = true;
    double olsrHello = 2.0;
    std::string kill = "relay";
    std::string outDir = ".";

    CommandLine cmd(__FILE__);
    cmd.AddValue("protocol", "Routing protocol: aodv or olsr", protocol);
    cmd.AddValue("run", "Run number (changes the random stream)", run);
    cmd.AddValue("simTime", "Simulation length (s)", simTime);
    cmd.AddValue("trafficStart", "When A starts sending (s); gives OLSR time to converge", trafficStart);
    cmd.AddValue("killTime", "When the relay is switched off (s)", killTime);
    cmd.AddValue("interval", "Time between packets (s)", interval);
    cmd.AddValue("deadline", "Deadline T (s). PLACEHOLDER until set from Kerala data", deadline);
    cmd.AddValue("window", "Length of the after-kill window that is scored separately (s)", window);
    cmd.AddValue("range", "Radio range (m)", range);
    cmd.AddValue("aodvHello", "AODV sends HELLO messages (ns-3 default: true)", aodvHello);
    cmd.AddValue("olsrHello", "OLSR HELLO interval (s) (ns-3 default: 2)", olsrHello);
    cmd.AddValue("kill", "Which node to switch off: relay (the one A is using), B or D", kill);
    cmd.AddValue("outDir", "Folder for the CSV outputs (must exist)", outDir);
    cmd.Parse(argc, argv);

    if (protocol != "aodv" && protocol != "olsr")
    {
        NS_FATAL_ERROR("--protocol must be aodv or olsr");
    }
    if (kill != "relay" && kill != "B" && kill != "D")
    {
        NS_FATAL_ERROR("--kill must be relay, B or D");
    }

    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(run);

    g_nodes.Create(4);

    MobilityHelper mobility;
    Ptr<ListPositionAllocator> positions = CreateObject<ListPositionAllocator>();
    positions->Add(Vector(0, 0, 0));    // A
    positions->Add(Vector(80, 60, 0));  // B
    positions->Add(Vector(160, 0, 0));  // C
    positions->Add(Vector(80, -60, 0)); // D
    mobility.SetPositionAllocator(positions);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(g_nodes);

    // Ad-hoc 802.11b. A hard range cut-off keeps the diamond shape exact; the
    // realistic propagation model comes later with the Kerala scenario.
    YansWifiChannelHelper channel;
    channel.SetPropagationDelay("ns3::ConstantSpeedPropagationDelayModel");
    channel.AddPropagationLoss("ns3::RangePropagationLossModel", "MaxRange", DoubleValue(range));
    YansWifiPhyHelper phy;
    phy.SetChannel(channel.Create());
    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211b);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",
                                 StringValue("DsssRate11Mbps"),
                                 "ControlMode",
                                 StringValue("DsssRate1Mbps"));
    WifiMacHelper mac;
    mac.SetType("ns3::AdhocWifiMac");
    g_devices = wifi.Install(phy, mac, g_nodes);

    InternetStackHelper internet;
    AodvHelper aodv;
    OlsrHelper olsr;
    Ipv4ListRoutingHelper list;
    if (protocol == "aodv")
    {
        aodv.Set("EnableHello", BooleanValue(aodvHello));
        internet.SetRoutingHelper(aodv);
        g_routingPort = 654;
    }
    else
    {
        olsr.Set("HelloInterval", TimeValue(Seconds(olsrHello)));
        list.Add(olsr, 100);
        internet.SetRoutingHelper(list);
        g_routingPort = 698;
    }
    internet.Install(g_nodes);

    Ipv4AddressHelper addresses;
    addresses.SetBase("10.1.1.0", "255.255.255.0");
    g_ifaces = addresses.Assign(g_devices);

    // Pre-fill every node's ARP table. Without this, B and D answer A's first route
    // request at the same instant and their ARP lookups collide, an artifact of the
    // perfectly symmetric simulation rather than of the routing protocol.
    NeighborCacheHelper neighborCache;
    neighborCache.PopulateNeighborCache();

    Ptr<Socket> rxSocket = Socket::CreateSocket(g_nodes.Get(C), UdpSocketFactory::GetTypeId());
    rxSocket->Bind(InetSocketAddress(Ipv4Address::GetAny(), DATA_PORT));
    rxSocket->SetRecvCallback(MakeCallback(&ReceivePacket));

    g_txSocket = Socket::CreateSocket(g_nodes.Get(A), UdpSocketFactory::GetTypeId());
    g_dest = InetSocketAddress(g_ifaces.GetAddress(C), DATA_PORT);
    g_interval = Seconds(interval);
    g_stopSending = Seconds(simTime - 1.0); // leave a second for the last packets to land
    Simulator::Schedule(Seconds(trafficStart), &SendPacket);

    Config::ConnectWithoutContext("/NodeList/*/$ns3::Ipv4L3Protocol/Tx", MakeCallback(&IpTx));
    Simulator::Schedule(Seconds(killTime), &KillNode, kill);

    Simulator::Stop(Seconds(simTime));
    Simulator::Run();

    // ---- Score the run ----
    uint32_t sent = g_seq;
    uint32_t received = g_rxTime.size();
    uint32_t withinT = 0;
    uint32_t sentWindow = 0;
    uint32_t withinTWindow = 0;
    double firstRxAfterKill = -1;

    std::string base = outDir + "/diamond-" + protocol + "-run" + std::to_string(run);
    std::ofstream packets(base + ".csv");
    packets << "seq,tx_s,rx_s,delay_ms,within_T\n";
    for (const auto& [seq, tx] : g_txTime)
    {
        auto it = g_rxTime.find(seq);
        bool got = it != g_rxTime.end();
        double delay = got ? it->second - tx : -1;
        bool ok = got && delay <= deadline;
        withinT += ok;
        if (tx >= killTime && tx < killTime + window)
        {
            sentWindow++;
            withinTWindow += ok;
        }
        if (got && it->second >= killTime && (firstRxAfterKill < 0 || it->second < firstRxAfterKill))
        {
            firstRxAfterKill = it->second;
        }
        packets << seq << "," << tx << "," << (got ? std::to_string(it->second) : "") << ","
                << (got ? std::to_string(delay * 1000) : "") << "," << ok << "\n";
    }
    packets.close();

    double recovery = firstRxAfterKill < 0 ? -1 : firstRxAfterKill - killTime;
    double controlRate = g_controlPackets / (4.0 * simTime);

    std::string summaryPath = outDir + "/diamond-summary.csv";
    bool newFile = !std::ifstream(summaryPath).good();
    std::ofstream summary(summaryPath, std::ios::app);
    if (newFile)
    {
        summary << "protocol,run,aodv_hello,olsr_hello_s,deadline_s,killed,sent,received,"
                   "delivery_ratio,within_T,within_T_after_kill,recovery_s,send_errors,"
                   "control_pkts,control_pkts_per_node_per_s\n";
    }
    summary << protocol << "," << run << "," << aodvHello << "," << olsrHello << "," << deadline
            << "," << NODE_NAME[g_victim] << "," << sent << "," << received << ","
            << (sent ? double(received) / sent : 0) << "," << (sent ? double(withinT) / sent : 0)
            << "," << (sentWindow ? double(withinTWindow) / sentWindow : 0) << "," << recovery
            << "," << g_sendErrors << "," << g_controlPackets << "," << controlRate << "\n";
    summary.close();

    std::cout << "\n" << protocol << " run " << run << " (killed " << NODE_NAME[g_victim] << " at "
              << killTime << " s, deadline T = " << deadline << " s)\n"
              << "  packets sent / received:        " << sent << " / " << received << "\n"
              << "  delivered within T (whole run): " << (sent ? 100.0 * withinT / sent : 0) << "%\n"
              << "  delivered within T (" << window << " s after kill): "
              << (sentWindow ? 100.0 * withinTWindow / sentWindow : 0) << "%\n"
              << "  route recovery time:            "
              << (recovery < 0 ? std::string("never recovered") : std::to_string(recovery) + " s")
              << "\n"
              << "  routing control packets:        " << g_controlPackets << " (" << controlRate
              << " per node per second)\n"
              << "  results: " << base << ".csv and " << summaryPath << "\n";

    Simulator::Destroy();
    return 0;
}
