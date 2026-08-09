package com.phoenix.monitor.data

data class Server(
    val name: String,
    val ip: String,
    val tailscaleIp: String,
    val role: String,
    val ports: List<PortCheck>,
    val isPrimary: Boolean = false,
)

data class PortCheck(
    val port: Int,
    val label: String,
    val path: String = "/",
)

data class ServerStatus(
    val server: Server,
    val hostReachable: Boolean,
    val portResults: Map<Int, Boolean>,
    val latencyMs: Long? = null,
    val checkedAt: Long = System.currentTimeMillis(),
)

data class AgentStatus(
    val id: String,
    val displayName: String,
    val emoji: String,
    val color: String,
    val soulLoaded: Boolean,
    val glyphBaselined: Boolean,
    val glyphAlerts: Int,
    val glyphSamples: Int,
    val ptyPort: Int,
)

data class LogEntry(
    val timestamp: String,
    val source: String,
    val level: String,
    val message: String,
)

val SERVERS = listOf(
    Server(
        name = "DarkPhoenix",
        tailscaleIp = "100.93.183.39",
        ip = "100.93.183.39",
        role = "Master — Agents, GPU, Voice",
        isPrimary = true,
        ports = listOf(
            PortCheck(9802, "Chat API"),
            PortCheck(9200, "K PTY"),
            PortCheck(9201, "Spear PTY"),
            PortCheck(9202, "Vesper PTY"),
            PortCheck(9203, "Qwen PTY"),
            PortCheck(9204, "Forge PTY"),
            PortCheck(9205, "Echo PTY"),
            PortCheck(9900, "Voice Bridge"),
            PortCheck(9903, "GPU TTS"),
        ),
    ),
    Server(
        name = "Home-Server",
        tailscaleIp = "100.81.237.29",
        ip = "100.81.237.29",
        role = "Standby — Laptop",
        ports = listOf(
            PortCheck(22, "SSH"),
        ),
    ),
    Server(
        name = "Dev-Machine",
        tailscaleIp = "100.95.219.37",
        ip = "100.95.219.37",
        role = "MiniPC — Dev",
        ports = listOf(
            PortCheck(22, "SSH"),
        ),
    ),
    Server(
        name = "Berlin",
        tailscaleIp = "100.71.89.61",
        ip = "87.106.137.147",
        role = "VPS — Cold Storage",
        ports = listOf(
            PortCheck(22, "SSH"),
            PortCheck(443, "HTTPS"),
        ),
    ),
)

val AGENT_PTY_MAP = mapOf(
    "k" to 9200,
    "spear" to 9201,
    "vesper" to 9202,
    "qwen" to 9203,
    "forge" to 9204,
    "echo" to 9205,
)
