package com.phoenix.monitor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.phoenix.monitor.ui.screens.DashboardScreen
import com.phoenix.monitor.ui.screens.DirectoryScreen
import com.phoenix.monitor.ui.screens.LogsScreen
import com.phoenix.monitor.ui.theme.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            MonitorContent()
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MonitorContent() {
    var selectedTab by remember { mutableIntStateOf(0) }

    val tabs = listOf("Dashboard", "Directory", "Logs")

    Scaffold(
        bottomBar = {
            NavigationBar(
                containerColor = PhoenixDark,
                tonalElevation = 8.dp,
            ) {
                tabs.forEachIndexed { index, title ->
                    NavigationBarItem(
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        label = {
                            Text(
                                title,
                                color = if (selectedTab == index) PhoenixFlame else PhoenixTextMuted,
                                fontSize = 12.sp,
                                fontWeight = if (selectedTab == index) FontWeight.Bold else FontWeight.Normal,
                            )
                        },
                        icon = {
                            Text(
                                when (index) {
                                    0 -> "\uD83C\uDFE0"
                                    1 -> "\uD83D\uDCCB"
                                    else -> "\uD83D\uDCDD"
                                },
                                fontSize = 18.sp,
                            )
                        },
                        colors = NavigationBarItemDefaults.colors(
                            indicatorColor = PhoenixFlame.copy(alpha = 0.15f),
                        ),
                    )
                }
            }
        },
        containerColor = PhoenixBlack,
    ) { padding ->
        Box(modifier = Modifier.padding(padding)) {
            when (selectedTab) {
                0 -> DashboardScreen()
                1 -> DirectoryScreen()
                2 -> LogsScreen()
            }
        }
    }
}
