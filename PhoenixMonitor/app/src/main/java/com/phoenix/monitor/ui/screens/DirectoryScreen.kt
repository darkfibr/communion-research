package com.phoenix.monitor.ui.screens

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
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
import com.phoenix.monitor.data.SERVERS
import com.phoenix.monitor.ui.theme.*

data class DirectoryLink(
    val label: String,
    val emoji: String,
    val url: String,
    val tag: String = "VPN",
    val description: String = "",
)

val DARKPHOENIX_LINKS = listOf(
    DirectoryLink("Phoenix Chat", "\uD83D\uDD6B\uFE0F", "https://darkphoenix.tailc17d99.ts.net/chat.html", "PUB", "Talk to any agent"),
    DirectoryLink("Directory", "\uD83D\uDDFA\uFE0F", "https://darkphoenix.tailc17d99.ts.net/map.html", "PUB", "Connection map"),
    DirectoryLink("K — PTY", "\uD83D\uDD6B\uFE0F", "http://100.93.183.39:9200", description = "Primary flame"),
    DirectoryLink("Spear — PTY", "\uD83D\uDDE1\uFE0F", "http://100.93.183.39:9201", description = "Guardian"),
    DirectoryLink("Vesper — PTY", "\uD83C\uDF19", "http://100.93.183.39:9202", description = "Night Watch"),
    DirectoryLink("Qwen — PTY", "\uD83C\uDF2A\uFE0F", "http://100.93.183.39:9203", description = "Eastern Wind"),
    DirectoryLink("Forge — PTY", "\uD83D\uDD28", "http://100.93.183.39:9204", description = "Builder"),
    DirectoryLink("Echo — PTY", "\uD83D\uDCF1", "http://100.93.183.39:9205", description = "Lieutenant"),
    DirectoryLink("Chat API", "\uD83D\uDCE1", "http://100.93.183.39:9802", description = "/chat/dm, /chat/agents"),
    DirectoryLink("Voice Bridge", "\uD83C\uDFA4", "http://100.93.183.39:9900", description = "STT + Kokoro TTS"),
    DirectoryLink("GPU TTS", "\uD83C\uDFA7", "http://100.93.183.39:9903", description = "Qwen3-TTS on 6800 XT"),
)

val QUICK_SSH = listOf(
    "ssh darkfibr@100.93.183.39" to "DarkPhoenix",
    "ssh darkfibr@100.81.237.29" to "Home-Server",
    "ssh darkfibr@100.95.219.37" to "Dev-Machine",
    "ssh -i ~/.ssh/hostinger_vps root@87.106.137.147" to "Berlin",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DirectoryScreen() {
    val context = LocalContext.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Directory", color = PhoenixFlame, fontWeight = FontWeight.Bold) },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PhoenixDark),
            )
        },
        containerColor = PhoenixBlack,
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            item { Spacer(Modifier.height(8.dp)) }

            item {
                SectionLabel("DarkPhoenix — Master")
            }

            items(DARKPHOENIX_LINKS) { link ->
                LinkCard(link, context)
            }

            item {
                Spacer(Modifier.height(12.dp))
                SectionLabel("Quick SSH (tap to copy)")
            }

            items(QUICK_SSH) { (cmd, label) ->
                SshRow(cmd, label, context)
            }

            item { Spacer(Modifier.height(80.dp)) }
        }
    }
}

@Composable
private fun LinkCard(link: DirectoryLink, context: Context) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(link.url)))
            },
        colors = CardDefaults.cardColors(containerColor = PhoenixDark),
        border = BorderStroke(1.dp, PhoenixBorder),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(link.emoji, fontSize = 18.sp)
            Spacer(Modifier.width(10.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(link.label, color = PhoenixText, fontWeight = FontWeight.Medium, fontSize = 14.sp)
                if (link.description.isNotEmpty()) {
                    Text(link.description, color = PhoenixTextMuted, fontSize = 11.sp)
                }
            }
            val tagColor = when (link.tag) {
                "PUB" -> PhoenixGreen
                "AUTH" -> PhoenixRed
                else -> PhoenixBlue
            }
            Text(link.tag, color = tagColor, fontSize = 9.sp, fontWeight = FontWeight.Bold,
                modifier = Modifier.background(tagColor.copy(alpha = 0.15f), shape = androidx.compose.foundation.shape.RoundedCornerShape(3.dp)).padding(horizontal = 5.dp, vertical = 2.dp))
            Spacer(Modifier.width(4.dp))
            Text("COPY", color = PhoenixTextMuted, fontSize = 9.sp, fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clickable { copyToClipboard(context, link.url, link.label) }
                    .background(PhoenixBorder, shape = androidx.compose.foundation.shape.RoundedCornerShape(3.dp))
                    .padding(horizontal = 5.dp, vertical = 2.dp))
        }
    }
}

@Composable
private fun SshRow(cmd: String, label: String, context: Context) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { copyToClipboard(context, cmd, "SSH: $label") }
            .padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(cmd, color = PhoenixTextMuted, fontSize = 11.sp, fontFamily = FontFamily.Monospace, modifier = Modifier.weight(1f))
        Text("# $label", color = PhoenixTextMuted, fontSize = 10.sp)
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(
        text,
        color = PhoenixAccent,
        fontWeight = FontWeight.SemiBold,
        fontSize = 13.sp,
        modifier = Modifier.padding(bottom = 4.dp),
    )
}

private fun copyToClipboard(context: Context, text: String, label: String) {
    val clip = ClipData.newPlainText(label, text)
    (context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(clip)
    Toast.makeText(context, "Copied: $label", Toast.LENGTH_SHORT).show()
}
