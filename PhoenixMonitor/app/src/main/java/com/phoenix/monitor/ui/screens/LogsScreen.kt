package com.phoenix.monitor.ui.screens

import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.phoenix.monitor.data.api.MonitorApiClient
import com.phoenix.monitor.ui.theme.*
import kotlinx.coroutines.launch
import java.io.File

data class LogLine(
    val timestamp: String,
    val level: String,
    val tag: String,
    val message: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LogsScreen() {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var logs by remember { mutableStateOf(listOf<LogLine>()) }
    var loading by remember { mutableStateOf(false) }
    var rawText by remember { mutableStateOf("") }

    suspend fun fetchLogs() {
        loading = true
        val sb = StringBuilder()
        val entries = mutableListOf<LogLine>()

        sb.appendLine("=== Phoenix Monitor — Diagnostic Export ===")
        sb.appendLine("Generated: ${java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss z", java.util.Locale.US).format(java.util.Date())}")
        sb.appendLine("Primary: ${MonitorApiClient.primaryUrl}")
        sb.appendLine()

        sb.appendLine("--- System Status ---")
        val sys = MonitorApiClient.fetchSystemStatus()
        if (sys != null) {
            sb.appendLine("Agents: ${sys.agents}")
            sb.appendLine("Dream running: ${sys.dream_running} (PID: ${sys.dream_pid})")
            sb.appendLine("Bridge files: ${sys.bridge_files} (${sys.bridge_size} bytes)")
            sb.appendLine("Glyph baselined: ${sys.glyph_baselined}, alerts: ${sys.glyph_alerts}")
            sb.appendLine("Model: ${sys.model}")
            sb.appendLine("Timestamp: ${sys.timestamp}")
            entries.add(LogLine(sys.timestamp, "INFO", "SYSTEM", "Dream=${sys.dream_running} Agents=${sys.agents} Bridge=${sys.bridge_files}"))
        } else {
            sb.appendLine("FAILED to fetch system status")
            entries.add(LogLine(now(), "ERROR", "SYSTEM", "Cannot reach primary"))
        }
        sb.appendLine()

        sb.appendLine("--- Agents ---")
        val agents = MonitorApiClient.fetchAgents()
        if (agents.isEmpty()) {
            sb.appendLine("No agents returned")
            entries.add(LogLine(now(), "WARN", "AGENTS", "Empty response"))
        } else {
            for (a in agents) {
                val line = "${a.emoji} ${a.displayName} | soul=${a.soulLoaded} glyph=${a.glyphBaselined} alerts=${a.glyphAlerts} pty=${a.ptyPort}"
                sb.appendLine(line)
                entries.add(LogLine(now(), "INFO", a.displayName.uppercase(), "soul=${a.soulLoaded} glyph=${a.glyphBaselined} alerts=${a.glyphAlerts}"))
            }
        }
        sb.appendLine()

        sb.appendLine("--- Server Connectivity ---")
        for (server in com.phoenix.monitor.data.SERVERS) {
            val (reachable, latency) = MonitorApiClient.pingHost(server.tailscaleIp)
            val status = if (reachable) "UP (${latency}ms)" else "DOWN"
            sb.appendLine("${server.name} (${server.tailscaleIp}): $status")
            entries.add(LogLine(now(), if (reachable) "INFO" else "ERROR", server.name.uppercase(), "$status role=${server.role}"))
        }

        rawText = sb.toString()
        logs = entries
        loading = false
    }

    LaunchedEffect(Unit) { fetchLogs() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Logs", color = PhoenixFlame, fontWeight = FontWeight.Bold) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PhoenixDark),
                actions = {
                    IconButton(onClick = { scope.launch { fetchLogs() } }) {
                        Text("\u21BB", fontSize = 20.sp, color = PhoenixText)
                    }
                    IconButton(onClick = { shareLogs(context, rawText) }) {
                        Text("Share", fontSize = 12.sp, color = PhoenixAccent)
                    }
                    IconButton(onClick = { copyLogs(context, rawText) }) {
                        Text("Copy", fontSize = 12.sp, color = PhoenixBlue)
                    }
                },
            )
        },
        containerColor = PhoenixBlack,
    ) { padding ->
        if (loading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = PhoenixFlame)
            }
        } else {
            LazyColumn(
                modifier = Modifier.padding(padding).padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                item { Spacer(Modifier.height(8.dp)) }
                items(logs) { log ->
                    LogRow(log)
                }
                item { Spacer(Modifier.height(80.dp)) }
            }
        }
    }
}

@Composable
private fun LogRow(log: LogLine) {
    val levelColor = when (log.level) {
        "ERROR" -> PhoenixRed
        "WARN" -> PhoenixYellow
        else -> PhoenixTextMuted
    }
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
    ) {
        Text(log.timestamp, color = PhoenixTextMuted, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        Spacer(Modifier.width(6.dp))
        Text(log.level, color = levelColor, fontSize = 10.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace)
        Spacer(Modifier.width(4.dp))
        Text(log.tag, color = PhoenixBlue, fontSize = 10.sp, fontFamily = FontFamily.Monospace)
        Spacer(Modifier.width(6.dp))
        Text(log.message, color = PhoenixText, fontSize = 11.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.weight(1f))
    }
}

private fun now(): String = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.US).format(java.util.Date())

private fun shareLogs(context: Context, text: String) {
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, text)
        putExtra(Intent.EXTRA_SUBJECT, "Phoenix Monitor Export")
    }
    context.startActivity(Intent.createChooser(intent, "Share logs via..."))
}

private fun copyLogs(context: Context, text: String) {
    val clip = android.content.ClipData.newPlainText("Phoenix Logs", text)
    (context.getSystemService(Context.CLIPBOARD_SERVICE) as android.content.ClipboardManager).setPrimaryClip(clip)
    android.widget.Toast.makeText(context, "Logs copied to clipboard", android.widget.Toast.LENGTH_SHORT).show()
}
