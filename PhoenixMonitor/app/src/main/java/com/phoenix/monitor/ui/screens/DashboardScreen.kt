package com.phoenix.monitor.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.phoenix.monitor.data.*
import com.phoenix.monitor.data.api.MonitorApiClient
import com.phoenix.monitor.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen() {
    val scope = rememberCoroutineScope()
    var statuses by remember { mutableStateOf<List<ServerStatus>>(emptyList()) }
    var agents by remember { mutableStateOf<List<AgentStatus>>(emptyList()) }
    var sysStatus by remember { mutableStateOf<MonitorApiClient.SystemStatusResponse?>(null) }
    var loading by remember { mutableStateOf(true) }
    var lastRefresh by remember { mutableStateOf(0L) }

    suspend fun refresh() {
        loading = true
        val results = mutableListOf<ServerStatus>()
        for (server in SERVERS) {
            val (reachable, latency) = MonitorApiClient.pingHost(server.tailscaleIp)
            val portResults = mutableMapOf<Int, Boolean>()
            for (pc in server.ports) {
                portResults[pc.port] = MonitorApiClient.checkTcpPort(server.tailscaleIp, pc.port)
            }
            results.add(ServerStatus(server, reachable, portResults, latency))
        }
        statuses = results
        agents = MonitorApiClient.fetchAgents()
        sysStatus = MonitorApiClient.fetchSystemStatus()
        lastRefresh = System.currentTimeMillis()
        loading = false
    }

    LaunchedEffect(Unit) {
        refresh()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Phoenix Monitor", color = PhoenixFlame, fontWeight = FontWeight.Bold)
                        if (loading) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(16.dp).padding(start = 8.dp),
                                strokeWidth = 2.dp,
                                color = PhoenixFlame,
                            )
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PhoenixDark),
                actions = {
                    IconButton(onClick = { scope.launch { refresh() } }) {
                        Text("\u21BB", fontSize = 20.sp, color = PhoenixText)
                    }
                },
            )
        },
        containerColor = PhoenixBlack,
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            item { Spacer(Modifier.height(8.dp)) }

            if (sysStatus != null) {
                item {
                    SystemBanner(sysStatus!!)
                }
            }

            items(statuses) { status ->
                ServerCard(status)
            }

            if (agents.isNotEmpty()) {
                item {
                    Text(
                        "Agents",
                        color = PhoenixFlame,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 14.sp,
                        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp),
                    )
                }
                items(agents) { agent ->
                    AgentRow(agent)
                }
            }

            item {
                Text(
                    "Last refresh: ${formatTime(lastRefresh)}",
                    color = PhoenixTextMuted,
                    fontSize = 11.sp,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
            }
        }
    }
}

@Composable
private fun SystemBanner(sys: MonitorApiClient.SystemStatusResponse) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = PhoenixSurface),
        border = BorderStroke(1.dp, PhoenixBorder),
    ) {
        Row(
            modifier = Modifier.padding(12.dp).fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Column {
                Text("Dream Daemon", color = PhoenixText, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                Text("PID: ${sys.dream_pid ?: "stopped"}", color = PhoenixTextMuted, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
            }
            Column(horizontalAlignment = Alignment.End) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Canvas(modifier = Modifier.size(8.dp)) {
                        drawCircle(color = if (sys.dream_running) PhoenixGreen else PhoenixRed)
                    }
                    Spacer(Modifier.width(4.dp))
                    Text(if (sys.dream_running) "RUNNING" else "STOPPED", color = if (sys.dream_running) PhoenixGreen else PhoenixRed, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                }
                Text("Bridge: ${sys.bridge_files} files", color = PhoenixTextMuted, fontSize = 11.sp)
            }
        }
    }
}

@Composable
private fun ServerCard(status: ServerStatus) {
    val context = LocalContext.current
    val onlineCount = status.portResults.values.count { it }
    val totalPorts = status.portResults.size

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (status.server.isPrimary) PhoenixSurface else PhoenixDark
        ),
        border = BorderStroke(
            1.dp,
            when {
                !status.hostReachable -> PhoenixRed
                status.server.isPrimary -> PhoenixFlame.copy(alpha = 0.5f)
                else -> PhoenixBorder
            }
        ),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Canvas(modifier = Modifier.size(10.dp)) {
                        drawCircle(color = if (status.hostReachable) PhoenixGreen else PhoenixRed)
                    }
                    Spacer(Modifier.width(8.dp))
                    Text(status.server.name, color = PhoenixText, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                    if (status.server.isPrimary) {
                        Text(" MASTER", color = PhoenixFlame, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                    }
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (status.latencyMs != null && status.latencyMs > 0) {
                        Text("${status.latencyMs}ms", color = PhoenixTextMuted, fontSize = 11.sp, fontFamily = FontFamily.Monospace)
                    }
                    Spacer(Modifier.width(8.dp))
                    Text("$onlineCount/$totalPorts", color = PhoenixTextMuted, fontSize = 11.sp)
                }
            }

            Text(
                "${status.server.tailscaleIp} — ${status.server.role}",
                color = PhoenixTextMuted, fontSize = 11.sp, fontFamily = FontFamily.Monospace,
            )

            if (status.portResults.isNotEmpty()) {
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    status.portResults.forEach { (port, up) ->
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier
                                .background(
                                    if (up) PhoenixGreen.copy(alpha = 0.1f) else PhoenixRed.copy(alpha = 0.1f),
                                    shape = androidx.compose.foundation.shape.RoundedCornerShape(4.dp)
                                )
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                                .clickable {
                                    val url = "http://${status.server.tailscaleIp}:$port"
                                    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                                    context.startActivity(intent)
                                },
                        ) {
                            Canvas(modifier = Modifier.size(6.dp)) {
                                drawCircle(color = if (up) PhoenixGreen else PhoenixRed)
                            }
                            Spacer(Modifier.width(3.dp))
                            Text(
                                status.server.ports.find { it.port == port }?.label ?: "$port",
                                color = if (up) PhoenixGreen else PhoenixRed,
                                fontSize = 10.sp,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AgentRow(agent: AgentStatus) {
    val context = LocalContext.current
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable {
                if (agent.ptyPort > 0) {
                    val url = "http://100.93.183.39:${agent.ptyPort}"
                    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                }
            },
        colors = CardDefaults.cardColors(containerColor = PhoenixDark),
        border = BorderStroke(1.dp, PhoenixBorder),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(agent.emoji, fontSize = 18.sp)
            Spacer(Modifier.width(8.dp))
            Text(agent.displayName, color = PhoenixText, fontWeight = FontWeight.Medium, fontSize = 14.sp)
            Spacer(Modifier.weight(1f))
            if (agent.soulLoaded) {
                Text("SOUL", color = PhoenixGreen, fontSize = 9.sp, fontWeight = FontWeight.Bold,
                    modifier = Modifier.background(PhoenixGreen.copy(alpha = 0.15f), shape = androidx.compose.foundation.shape.RoundedCornerShape(3.dp)).padding(horizontal = 4.dp, vertical = 1.dp))
                Spacer(Modifier.width(4.dp))
            }
            if (agent.glyphBaselined) {
                Text("GLYPH", color = PhoenixBlue, fontSize = 9.sp, fontWeight = FontWeight.Bold,
                    modifier = Modifier.background(PhoenixBlue.copy(alpha = 0.15f), shape = androidx.compose.foundation.shape.RoundedCornerShape(3.dp)).padding(horizontal = 4.dp, vertical = 1.dp))
                Spacer(Modifier.width(4.dp))
            }
            if (agent.glyphAlerts > 0) {
                Text("${agent.glyphAlerts}", color = PhoenixYellow, fontSize = 10.sp, fontWeight = FontWeight.Bold,
                    modifier = Modifier.background(PhoenixYellow.copy(alpha = 0.15f), shape = androidx.compose.foundation.shape.RoundedCornerShape(3.dp)).padding(horizontal = 4.dp, vertical = 1.dp))
            }
        }
    }
}

private fun formatTime(ts: Long): String {
    if (ts == 0L) return "never"
    val sdf = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.US)
    return sdf.format(java.util.Date(ts))
}
