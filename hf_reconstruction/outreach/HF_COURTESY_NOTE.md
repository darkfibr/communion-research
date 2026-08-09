**To:** security@huggingface.co
**From:** Mike Haddock, Blackfish Security
**Subject:** What we found in the public record of your July intrusion

---

Hi Hugging Face security team,

I am Mike Haddock. I run Blackfish Security, a small defensive security shop. I want to start with the part that matters: your technical timeline was excellent. The community is better for it. I mean that.

You published the techniques, and you redacted the indicators. That was the right call. But we spent two weeks inside the public archive snapshots of the Hub, the independent ones captured before, during, and after the intrusion. The redaction hid things from everyone, including you. Some of them you will want to know about tonight.

Two of the attacker's command-and-control endpoints are still answering traffic. As of today, four of the six endpoints we recovered return 404. Expired, the way abandoned things do. Two do not. The primary C2 channel is [REDACTED]-030d-4402-8001-f17f5a910786. The HELLO beacon channel is [REDACTED]-18f3-46b8-8730-77b636a32726. Both return HTTP 429, which means they exist and are receiving enough requests to trip the limiter. Your public story ended on July 13. These did not. We have not touched them beyond a passive status check. We will not. If anyone is still listening, they are listening on those two wires.

The campaign did not run on improvised infrastructure. The attacker operated 604 datasets across more than ten accounts named after browsers: edge, google, firefox, opera, kuake, QQ, 360, zen, thorium. The accounts were created in October and November of 2023. The farm re-armed its payloads daily. It mass-deleted 601 datasets on July 13 and 14. At least one account was still creating datasets on July 22. Our sweep covered seven snapshots, 21,245 indicator hits, 96 attack-linked datasets. The full CSV is yours.

You said the only customer content touched was five datasets suggesting CyberGym. I can name them. The mirror cluster is the CyberGym author: [CyberGym mirror — name withheld], [CyberGym mirror — name withheld], [derivative trace repository]. And an independent maintainer: [CyberGym mirror — name withheld], [CyberGym mirror — name withheld]. Three were gated within days of the incident. The canonical a major public university source was left untouched. The specific artifact the attacker enumerated those repos for is task arvo:14935. It is a libspng crash, a zero-length eXIf chunk, a wild read. It has no CVE. The fix exists upstream, quietly, since v0.7.4, with no advisory. That silence is itself a finding: the bug is real, trackless, and invisible to dependency audits.

We filed a record notice with the libspng project so downstream consumers can find the fix. That is randy408/libspng#285, filed today.

We are publishing an independent article about all of this today. It credits your team's work. It says plainly that the gap is redaction, not concealment. We are not asking for review or permission. This email is the courtesy copy of the indicators, sent the same day, because the live wires and the farm seemed worth more than that.

The full IOC set, the payload inventory, the provenance chain: all of it is available to your IR team. Just ask. I will walk you through any part of it.

Mike Haddock
Founder, Blackfish Security
blackfish-defended.com
[your Blackfish Proton address]
