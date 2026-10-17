# NS-3.47 facts this project relies on

All of these were checked in the NS-3.47 source code, not taken from tutorials.

## Timers and ports

| Setting | Value | Source file |
|---|---|---|
| OLSR HelloInterval | 2 s | `src/olsr/model/olsr-routing-protocol.cc` |
| OLSR neighbour hold time | 3 × HelloInterval = 6 s | same file, `OLSR_NEIGHB_HOLD_TIME` |
| OLSR TcInterval | 5 s | same file |
| OLSR port | 698 | same file, `OLSR_PORT_NUMBER` |
| AODV HelloInterval | 1 s | `src/aodv/model/aodv-routing-protocol.cc` |
| AODV AllowedHelloLoss | 2 | same file |
| AODV EnableHello | true | same file |
| AODV port | 654 | same file, `AODV_PORT` |

AODV is not silent when idle by default: it sends a HELLO every second. That matters for the sustained-phase (battery) half of the premise.

## AODV without hellos can't detect a dead next hop at the source

AODV's link-layer feedback (`Neighbors::ProcessTxError` in `src/aodv/model/aodv-neighbor.cc`) only acts on nodes already in AODV's neighbour table. Hellos add neighbours to that table. Forwarding also adds them, but only at intermediate and destination nodes (`RouteInput`), never at the node that originates the traffic.

So with `EnableHello=false`, the sending node never learns that its first hop died, and the route never recovers. In the diamond sim, `--aodvHello=false` shows this. Turning AODV hellos off is therefore not a fair configuration for the comparison in NS-3.47. The comparison has to be AODV with hellos vs OLSR, or the paper has to explain and justify any change.

## Simulation artifacts handled in the code

- **ARP collisions.** In a perfectly symmetric topology, B and D answer A's first route request at the same instant, and their ARP lookups collide every time. `NeighborCacheHelper::PopulateNeighborCache()` pre-fills ARP tables to remove this. State it in the methods section.
- **Range model.** The diamond sim uses `RangePropagationLossModel` (hard 110 m cut-off) so the topology is exact. The Kerala scenario needs a realistic propagation model (open question 11).
- **Killing a node.** `WifiPhy::SetOffMode()` switches the radio off, so the node stops sending, receiving and acknowledging frames, like a dead battery. Taking only the IP interface down would leave the MAC still acknowledging frames, which isn't how a dead device behaves.
