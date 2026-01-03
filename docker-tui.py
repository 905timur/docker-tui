"""
Docker TUI - Interactive Container Monitor
===========================================

A Python-based Docker TUI with:
- Container listing with real-time stats (CPU, memory, uptime)
- Interactive logs and statistics view for selected containers
- Container management (start, stop, restart, remove)

Keybindings:
------------
Main view:
  l - Show logs and stats for selected container
  r - Restart container
  s - Stop container
  t - Start container
  d - Remove container
  f - Toggle filter (all/running only)
  q - Quit

Logs view:
  q or ESC - Return to main container list
"""

import asyncio
from docker import from_env
from docker.errors import DockerException
from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, Footer, Static, RichLog
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding
from rich.text import Text
from datetime import datetime
from textual import events

client = from_env()

class StatsBar(Static):
    """Display overall Docker stats"""
    
    def compose(self) -> ComposeResult:
        yield Static("", id="stats-content")
    
    def update_stats(self, total: int, running: int, stopped: int, paused: int):
        stats_text = Text()
        stats_text.append("Containers: ", style="bold cyan")
        stats_text.append(f"{total} ", style="bold white")
        stats_text.append("Running: ", style="bold green")
        stats_text.append(f"{running} ", style="bold white")
        stats_text.append("Stopped: ", style="bold red")
        stats_text.append(f"{stopped} ", style="bold white")
        if paused > 0:
            stats_text.append("Paused: ", style="bold yellow")
            stats_text.append(f"{paused} ", style="bold white")
        
        stats_text.append(" │ ", style="dim")
        stats_text.append(f"Last update: {datetime.now().strftime('%H:%M:%S')}", style="dim italic")
        
        self.query_one("#stats-content", Static).update(stats_text)


class LogsView(Container):
    """Container logs and stats view"""
    
    def __init__(self, container_id: str, container_name: str):
        super().__init__(id="logs-view")
        self.container_id = container_id
        self.container_name = container_name
        self.log_task = None
        self.stats_task = None
        self.running = False
    
    def compose(self) -> ComposeResult:
        """Create the logs view layout"""
        # Container info and stats panel
        yield Static(f"Container: {self.container_name}", id="container-header")
        yield Static("Loading stats...", id="container-stats")
        
        # Logs panel
        yield RichLog(id="logs-panel", wrap=True, highlight=True, markup=True)
        yield Static("Press [bold cyan]q[/] or [bold cyan]ESC[/] to return to container list", id="logs-footer")
    
    async def on_mount(self):
        """Start log streaming and stats updates when view is mounted"""
        self.running = True
        
        # Get widgets
        self.logs_panel = self.query_one("#logs-panel", RichLog)
        self.stats_widget = self.query_one("#container-stats", Static)
        
        # Start background tasks
        self.log_task = asyncio.create_task(self._stream_logs())
        self.stats_task = asyncio.create_task(self._update_stats())
    
    async def _stream_logs(self):
        """Stream container logs in real-time"""
        try:
            container = client.containers.get(self.container_id)
            
            # Get last 100 lines of logs
            self.logs_panel.write("[dim]Loading last 100 log lines...[/dim]")
            initial_logs = container.logs(tail=100, timestamps=True).decode('utf-8', errors='replace')
            
            for line in initial_logs.strip().split('\n'):
                if line:
                    self.logs_panel.write(line)
            
            self.logs_panel.write("[dim]--- Streaming new logs ---[/dim]")
            
            # Stream new logs
            log_stream = container.logs(stream=True, follow=True, timestamps=True)
            
            for log_line in log_stream:
                if not self.running:
                    break
                
                decoded_line = log_line.decode('utf-8', errors='replace').strip()
                if decoded_line:
                    self.logs_panel.write(decoded_line)
                
                # Allow other tasks to run
                await asyncio.sleep(0.01)
        
        except Exception as e:
            self.logs_panel.write(f"[bold red]Error streaming logs: {str(e)}[/bold red]")
    
    async def _update_stats(self):
        """Update container stats periodically"""
        while self.running:
            try:
                container = client.containers.get(self.container_id)
                
                # Check if container is running
                container.reload()
                if container.status != "running":
                    stats_text = Text()
                    stats_text.append("Status: ", style="bold yellow")
                    stats_text.append(f"{container.status}", style="yellow")
                    self.stats_widget.update(stats_text)
                    await asyncio.sleep(2)
                    continue
                
                # Get stats (non-streaming)
                stats = container.stats(stream=False)
                
                # Calculate CPU percentage
                cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                           stats['precpu_stats']['cpu_usage']['total_usage']
                system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                              stats['precpu_stats']['system_cpu_usage']
                
                cpu_percent = 0.0
                if system_delta > 0 and cpu_delta > 0:
                    num_cpus = len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [1]))
                    cpu_percent = (cpu_delta / system_delta) * num_cpus * 100
                
                # Calculate memory usage
                mem_usage = stats['memory_stats'].get('usage', 0)
                mem_limit = stats['memory_stats'].get('limit', 0)
                
                # Format memory
                def format_bytes(bytes_val):
                    if bytes_val >= 1024**3:
                        return f"{bytes_val / 1024**3:.2f}GB"
                    elif bytes_val >= 1024**2:
                        return f"{bytes_val / 1024**2:.1f}MB"
                    else:
                        return f"{bytes_val / 1024:.1f}KB"
                
                # Create stats display
                stats_text = Text()
                stats_text.append("CPU: ", style="bold cyan")
                stats_text.append(f"{cpu_percent:.1f}%", style="bold green" if cpu_percent < 50 else "bold yellow")
                stats_text.append("  │  ", style="dim")
                stats_text.append("Memory: ", style="bold cyan")
                stats_text.append(f"{format_bytes(mem_usage)}", style="bold white")
                stats_text.append(" / ", style="dim")
                stats_text.append(f"{format_bytes(mem_limit)}", style="bold white")
                
                # Memory percentage
                if mem_limit > 0:
                    mem_percent = (mem_usage / mem_limit) * 100
                    stats_text.append(f" ({mem_percent:.1f}%)", style="dim")
                
                self.stats_widget.update(stats_text)
                
            except Exception as e:
                # Container might have stopped
                stats_text = Text()
                stats_text.append("Error: ", style="bold red")
                stats_text.append(str(e), style="red")
                self.stats_widget.update(stats_text)
            
            # Update every 1.5 seconds
            await asyncio.sleep(1.5)
    
    async def cleanup(self):
        """Cancel background tasks when leaving view"""
        self.running = False
        
        if self.log_task and not self.log_task.done():
            self.log_task.cancel()
            try:
                await self.log_task
            except asyncio.CancelledError:
                pass
        
        if self.stats_task and not self.stats_task.done():
            self.stats_task.cancel()
            try:
                await self.stats_task
            except asyncio.CancelledError:
                pass


class DockerTUI(App):
    CSS = """
    Screen {
        background: $surface;
    }
    
    Header {
        background: $primary;
        color: $text;
        text-style: bold;
    }
    
    Footer {
        background: $panel;
    }
    
    #stats-bar {
        height: 3;
        background: $panel;
        border: solid $primary;
        padding: 1;
        margin-bottom: 1;
    }
    
    #main-container {
        height: 100%;
    }
    
    DataTable {
        height: 100%;
        border: solid $accent;
    }
    
    DataTable > .datatable--cursor {
        background: $accent 30%;
    }
    
    DataTable > .datatable--header {
        background: $primary;
        color: $text;
        text-style: bold;
    }
    
    DataTable > .datatable--odd-row {
        background: $surface;
    }
    
    DataTable > .datatable--even-row {
        background: $panel;
    }
    
    DataTable:focus > .datatable--cursor {
        background: $accent 50%;
    }
    
    /* Logs view styling */
    #logs-view {
        height: 100%;
        background: $surface;
    }
    
    #container-header {
        height: 3;
        background: $primary;
        color: $text;
        text-style: bold;
        padding: 1;
        border: solid $accent;
    }
    
    #container-stats {
        height: 3;
        background: $panel;
        padding: 1;
        border: solid $primary;
        margin-bottom: 1;
    }
    
    #logs-panel {
        height: 1fr;
        background: $surface;
        border: solid $accent;
        padding: 1;
    }
    
    #logs-footer {
        height: 1;
        background: $panel;
        text-align: center;
        padding: 0 1;
    }
    """
    
    TITLE = "Docker TUI - Container Monitor"
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "restart_container", "Restart"),
        Binding("s", "stop_container", "Stop"),
        Binding("t", "start_container", "Start"),
        Binding("d", "remove_container", "Remove"),
        Binding("l", "logs", "Logs"),
        Binding("f", "toggle_filter", "Filter"),
    ]
    
    def __init__(self):
        super().__init__()
        self.show_all = True
        self.container_ids = {}
        self.current_logs_view = None  # Track active logs view
        self.in_logs_view = False  # UI state flag
    
    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield StatsBar(id="stats-bar")
        with Vertical(id="main-container"):
            yield DataTable(cursor_type="row", zebra_stripes=True)
        yield Footer()
    
    def on_mount(self):
        self.table = self.query_one(DataTable)
        self.stats_bar = self.query_one(StatsBar)
        
        # Setup table columns with better formatting
        self.table.add_columns(
            "ID", "NAME", "STATUS", "IMAGE", "PORTS", "CPU %", "MEM", "UPTIME"
        )
        self.table.cursor_type = "row"
        self.table.zebra_stripes = True
        
        # Start periodic refresh
        self.set_interval(10.0, self.refresh_data)
        self.refresh_data()
    
    def refresh_data(self):
        """Refresh container data"""
        try:
            self.table.clear()
            self.container_ids.clear()
            
            containers = client.containers.list(all=self.show_all)
            
            # Calculate stats
            running = sum(1 for c in containers if c.status == "running")
            stopped = sum(1 for c in containers if c.status == "exited")
            paused = sum(1 for c in containers if c.status == "paused")
            
            self.stats_bar.update_stats(len(containers), running, stopped, paused)
            
            for idx, c in enumerate(containers):
                # Store container ID for actions
                self.container_ids[idx] = c.id
                
                # Short ID
                short_id = c.short_id
                
                # Container name
                name = Text(c.name, style="bold cyan")
                
                # Status with color coding
                status = c.status
                if status == "running":
                    status_text = Text("● running", style="bold green")
                elif status == "exited":
                    status_text = Text("■ exited", style="bold red")
                elif status == "paused":
                    status_text = Text("‖ paused", style="bold yellow")
                else:
                    status_text = Text(f"○ {status}", style="dim")
                
                # Image name (shortened)
                image = c.image.tags[0] if c.image.tags else c.image.short_id
                if len(image) > 30:
                    image = image[:27] + "..."
                
                # Port mappings
                ports = ""
                if c.ports:
                    port_list = []
                    for container_port, host_bindings in c.ports.items():
                        if host_bindings:
                            for binding in host_bindings:
                                port_list.append(f"{binding['HostPort']}→{container_port}")
                        else:
                            port_list.append(str(container_port))
                    ports = ", ".join(port_list[:2])  # Limit to 2 ports
                    if len(c.ports) > 2:
                        ports += "..."
                
                # Get stats for running containers
                cpu_usage = "-"
                mem_usage = "-"
                if status == "running":
                    try:
                        stats = c.stats(stream=False)
                        
                        # CPU calculation
                        cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                                   stats['precpu_stats']['cpu_usage']['total_usage']
                        system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                                      stats['precpu_stats']['system_cpu_usage']
                        if system_delta > 0:
                            cpu_percent = (cpu_delta / system_delta) * \
                                        len(stats['cpu_stats']['cpu_usage'].get('percpu_usage', [1])) * 100
                            cpu_usage = f"{cpu_percent:.1f}"
                        
                        # Memory calculation
                        mem_usage_bytes = stats['memory_stats']['usage']
                        if mem_usage_bytes > 1024**3:
                            mem_usage = f"{mem_usage_bytes / 1024**3:.1f}G"
                        else:
                            mem_usage = f"{mem_usage_bytes / 1024**2:.0f}M"
                    except:
                        pass
                
                # Uptime
                created = c.attrs['Created']
                uptime = self._format_uptime(created) if status == "running" else "-"
                
                self.table.add_row(
                    short_id,
                    name,
                    status_text,
                    image,
                    ports or "-",
                    cpu_usage,
                    mem_usage,
                    uptime,
                    key=str(idx)
                )
        
        except DockerException as e:
            self.notify(f"Docker error: {str(e)}", severity="error")
    
    def _format_uptime(self, created_str: str) -> str:
        """Format container uptime"""
        try:
            created = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            delta = datetime.now(created.tzinfo) - created
            
            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60
            
            if days > 0:
                return f"{days}d{hours}h"
            elif hours > 0:
                return f"{hours}h{minutes}m"
            else:
                return f"{minutes}m"
        except:
            return "-"
    
    def action_toggle_filter(self):
        """Toggle between all containers and running only"""
        self.show_all = not self.show_all
        filter_text = "all" if self.show_all else "running only"
        self.notify(f"Showing: {filter_text}", timeout=1)
        self.refresh_data()
    
    def action_restart_container(self):
        """Restart selected container"""
        if self.table.cursor_row >= 0:
            try:
                container_id = self.container_ids[self.table.cursor_row]
                container = client.containers.get(container_id)
                container.restart()
                self.notify(f"Restarting {container.name}", timeout=2)
            except Exception as e:
                self.notify(f"Error: {str(e)}", severity="error")
    
    def action_stop_container(self):
        """Stop selected container"""
        if self.table.cursor_row >= 0:
            try:
                container_id = self.container_ids[self.table.cursor_row]
                container = client.containers.get(container_id)
                container.stop()
                self.notify(f"Stopping {container.name}", timeout=2)
            except Exception as e:
                self.notify(f"Error: {str(e)}", severity="error")
    
    def action_start_container(self):
        """Start selected container"""
        if self.table.cursor_row >= 0:
            try:
                container_id = self.container_ids[self.table.cursor_row]
                container = client.containers.get(container_id)
                container.start()
                self.notify(f"Starting {container.name}", timeout=2)
            except Exception as e:
                self.notify(f"Error: {str(e)}", severity="error")
    
    def action_remove_container(self):
        """Remove selected container"""
        if self.table.cursor_row >= 0:
            try:
                container_id = self.container_ids[self.table.cursor_row]
                container = client.containers.get(container_id)
                name = container.name
                container.remove(force=True)
                self.notify(f"Removed {name}", severity="warning", timeout=2)
            except Exception as e:
                self.notify(f"Error: {str(e)}", severity="error")
    
    async def action_logs(self):
        """Show container logs and stats"""
        # Only allow from table view
        if self.in_logs_view:
            return
        
        if self.table.cursor_row >= 0:
            try:
                container_id = self.container_ids[self.table.cursor_row]
                container = client.containers.get(container_id)
                
                # Switch to logs view
                await self._show_logs_view(container_id, container.name)
            except Exception as e:
                self.notify(f"Error: {str(e)}", severity="error")
        else:
            self.notify("No container selected", timeout=2)
    
    async def _show_logs_view(self, container_id: str, container_name: str):
        """Switch to logs view for specified container"""
        # Hide main container and stats bar
        self.query_one("#main-container").display = False
        self.query_one("#stats-bar").display = False
        
        # Create and mount logs view
        self.current_logs_view = LogsView(container_id, container_name)
        await self.mount(self.current_logs_view)
        
        # Update state
        self.in_logs_view = True
    
    async def _hide_logs_view(self):
        """Return to main container table"""
        if self.current_logs_view:
            # Clean up background tasks
            await self.current_logs_view.cleanup()
            
            # Remove logs view
            await self.current_logs_view.remove()
            self.current_logs_view = None
        
        # Show main container and stats bar
        self.query_one("#main-container").display = True
        self.query_one("#stats-bar").display = True
        
        # Update state
        self.in_logs_view = False
        
        # Refresh table data
        self.refresh_data()
    
    async def on_key(self, event: events.Key) -> None:
        """Handle key presses for logs view navigation"""
        # Handle 'q' or 'Escape' in logs view
        if self.in_logs_view and event.key in ("q", "escape"):
            await self._hide_logs_view()
            event.prevent_default()
            event.stop()


if __name__ == "__main__":
    app = DockerTUI()
    app.run()