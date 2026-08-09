package com.phoenix.monitor.data.api

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import com.phoenix.monitor.data.AgentStatus
import kotlinx.coroutines.*
import okhttp3.OkHttpClient
import okhttp3.Request
import java.net.InetSocketAddress
import java.net.Socket

object MonitorApiClient {

    var primaryUrl: String = "http://100.93.183.39:9802"
    var authToken: String = "Jay4480"

    private val gson = Gson()
    private val client = OkHttpClient.Builder()
        .connectTimeout(6, java.util.concurrent.TimeUnit.SECONDS)
        .readTimeout(10, java.util.concurrent.TimeUnit.SECONDS)
        .build()

    private val pingClient = OkHttpClient.Builder()
        .connectTimeout(3, java.util.concurrent.TimeUnit.SECONDS)
        .readTimeout(3, java.util.concurrent.TimeUnit.SECONDS)
        .build()

    suspend fun checkTcpPort(ip: String, port: Int): Boolean = withContext(Dispatchers.IO) {
        try {
            Socket().use { socket ->
                socket.connect(InetSocketAddress(ip, port), 3000)
                true
            }
        } catch (_: Exception) {
            false
        }
    }

    suspend fun pingHost(ip: String): Pair<Boolean, Long> = withContext(Dispatchers.IO) {
        try {
            val start = System.currentTimeMillis()
            val req = Request.Builder()
                .url("http://$ip:9802/chat/agents")
                .header("Authorization", "Bearer $authToken")
                .get()
                .build()
            pingClient.newCall(req).execute().use { resp ->
                val elapsed = System.currentTimeMillis() - start
                Pair(resp.isSuccessful, elapsed)
            }
        } catch (_: Exception) {
            try {
                val start = System.currentTimeMillis()
                Socket().use { socket ->
                    socket.connect(InetSocketAddress(ip, 22), 3000)
                }
                val elapsed = System.currentTimeMillis() - start
                Pair(true, elapsed)
            } catch (_: Exception) {
                Pair(false, -1L)
            }
        }
    }

    suspend fun fetchAgents(): List<AgentStatus> = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder()
                .url("$primaryUrl/chat/agents")
                .header("Authorization", "Bearer $authToken")
                .get()
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@withContext emptyList()
                val body = resp.body?.string() ?: return@withContext emptyList()
                val agentsResp = gson.fromJson(body, AgentsResponse::class.java)
                agentsResp.agents.map { a ->
                    AgentStatus(
                        id = a.id,
                        displayName = a.display_name,
                        emoji = a.emoji,
                        color = a.color,
                        soulLoaded = a.soul_loaded,
                        glyphBaselined = a.glyph?.baselined ?: false,
                        glyphAlerts = a.glyph?.alerts ?: 0,
                        glyphSamples = a.glyph?.samples ?: 0,
                        ptyPort = when (a.id) {
                            "k" -> 9200; "spear" -> 9201; "vesper" -> 9202
                            "qwen" -> 9203; "forge" -> 9204; "echo" -> 9205
                            else -> 0
                        },
                    )
                }
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    suspend fun fetchSystemStatus(): SystemStatusResponse? = withContext(Dispatchers.IO) {
        try {
            val req = Request.Builder()
                .url("$primaryUrl/chat/system/status")
                .header("Authorization", "Bearer $authToken")
                .get()
                .build()
            client.newCall(req).execute().use { resp ->
                if (!resp.isSuccessful) return@withContext null
                val body = resp.body?.string() ?: return@withContext null
                gson.fromJson(body, SystemStatusResponse::class.java)
            }
        } catch (_: Exception) {
            null
        }
    }

    data class AgentsResponse(val agents: List<AgentJson>)
    data class AgentJson(
        val id: String,
        val display_name: String,
        val emoji: String,
        val color: String,
        val soul_loaded: Boolean,
        val glyph: GlyphJson?,
    )
    data class GlyphJson(val samples: Int, val alerts: Int, val baselined: Boolean)
    data class SystemStatusResponse(
        val agents: Int,
        val dream_running: Boolean,
        val dream_pid: String?,
        val bridge_files: Int,
        val bridge_size: Int,
        val glyph_baselined: Int,
        val glyph_alerts: Int,
        val model: String,
        val timestamp: String,
    )
}
