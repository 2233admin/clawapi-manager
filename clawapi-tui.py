#!/usr/bin/env python3
"""
ClawAPI Manager TUI - 配置管理面板
三个模块：Models、Channels、Skills
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Static, TabbedContent, TabPane, DataTable, Input, Label
from textual.binding import Binding
import sys
import os

# 添加 lib 目录
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from config_manager import ClawAPIConfigManager

class ClawAPITUI(App):
    """ClawAPI Manager TUI"""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #status-bar {
        dock: top;
        height: 3;
        background: $primary;
        color: $text;
        padding: 1;
    }
    
    DataTable {
        height: 100%;
    }
    
    .button-row {
        height: 3;
        padding: 1;
    }
    
    Button {
        margin: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
    ]
    
    def __init__(self):
        super().__init__()
        self.manager = ClawAPIConfigManager()
    
    def compose(self) -> ComposeResult:
        """创建界面"""
        yield Header()
        
        # 状态栏
        yield Static(id="status-bar", markup=True)
        
        # 主内容区（三个标签页）
        with TabbedContent():
            # Models 标签页
            with TabPane("Models", id="models-tab"):
                yield DataTable(id="models-table")
                with Horizontal(classes="button-row"):
                    yield Button("Add Provider", id="add-provider", variant="primary")
                    yield Button("Add Model", id="add-model")
                    yield Button("Set Primary", id="set-primary")
                    yield Button("Test", id="test-provider")
            
            # Channels 标签页
            with TabPane("Channels", id="channels-tab"):
                yield DataTable(id="channels-table")
                with Horizontal(classes="button-row"):
                    yield Button("Add Channel", id="add-channel", variant="primary")
                    yield Button("Edit", id="edit-channel")
                    yield Button("Remove", id="remove-channel")
                    yield Button("Test", id="test-channel")
            
            # Skills 标签页
            with TabPane("Skills", id="skills-tab"):
                yield DataTable(id="skills-table")
                with Horizontal(classes="button-row"):
                    yield Button("Install", id="install-skill", variant="primary")
                    yield Button("Update", id="update-skill")
                    yield Button("Remove", id="remove-skill")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """挂载时初始化"""
        self.update_status()
        self.load_models()
        self.load_channels()
        self.load_skills()
    
    def update_status(self):
        """更新状态栏"""
        primary = self.manager.get_primary_model()
        fallbacks = self.manager.get_fallbacks()
        providers = self.manager.list_providers()
        
        status_text = f"[bold]Primary:[/bold] {primary}  |  [bold]Providers:[/bold] {len(providers)}  |  [bold]Fallbacks:[/bold] {len(fallbacks)}"
        self.query_one("#status-bar", Static).update(status_text)
    
    def load_models(self):
        """加载 Models 数据"""
        table = self.query_one("#models-table", DataTable)
        table.clear(columns=True)
        
        # 添加列
        table.add_columns("Provider", "Models", "API Key", "Status")
        
        # 添加数据
        for provider in self.manager.list_providers():
            table.add_row(
                provider['name'],
                str(provider['model_count']),
                provider['api_key'],
                "✅"
            )
    
    def load_channels(self):
        """加载 Channels 数据"""
        table = self.query_one("#channels-table", DataTable)
        table.clear(columns=True)
        
        # 添加列
        table.add_columns("Channel", "Type", "Status", "Config")
        
        # 读取 channels 配置
        config = self.manager._load_config()
        channels = config.get('channels', {})
        
        # 添加数据
        for name, channel_config in channels.items():
            enabled = channel_config.get('enabled', False)
            channel_type = channel_config.get('type', 'unknown')
            
            table.add_row(
                name,
                channel_type,
                "✅ Enabled" if enabled else "❌ Disabled",
                "Configured"
            )
        
        # 如果没有 channels，显示提示
        if not channels:
            table.add_row("(No channels configured)", "", "", "")
    
    def load_skills(self):
        """加载 Skills 数据"""
        table = self.query_one("#skills-table", DataTable)
        table.clear(columns=True)
        
        # 添加列
        table.add_columns("Skill", "Version", "Status", "Location")
        
        # 扫描 skills 目录
        import subprocess
        try:
            result = subprocess.run(
                ['clawhub', 'list'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # 解析输出
                for line in result.stdout.split('\n'):
                    if line.strip() and not line.startswith('─'):
                        parts = line.split()
                        if len(parts) >= 2:
                            table.add_row(parts[0], parts[1] if len(parts) > 1 else "?", "✅", "ClawHub")
            else:
                table.add_row("(Run 'clawhub list' to see skills)", "", "", "")
        except:
            table.add_row("(clawhub not available)", "", "", "")
    
    def action_refresh(self):
        """刷新数据"""
        self.update_status()
        self.load_models()
        self.load_channels()
        self.load_skills()
        self.notify("Refreshed")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """按钮点击事件"""
        button_id = event.button.id
        
        if button_id == "add-provider":
            self.notify("Add Provider: Use CLI - ./clawapi add-provider <name> <url> <key>")
        
        elif button_id == "add-model":
            self.notify("Add Model: Use CLI - ./clawapi add-model <provider> <id> <name>")
        
        elif button_id == "set-primary":
            self.notify("Set Primary: Use CLI - ./clawapi set-primary <model_id>")
        
        elif button_id == "test-provider":
            # 获取选中的 provider
            table = self.query_one("#models-table", DataTable)
            if table.cursor_row < len(table.rows):
                provider_name = table.get_row_at(table.cursor_row)[0]
                try:
                    result = self.manager.test_provider(provider_name)
                    if result['success']:
                        self.notify(f"✅ {provider_name} OK")
                    else:
                        self.notify(f"❌ {provider_name} Failed: {result.get('error', 'Unknown')}")
                except Exception as e:
                    self.notify(f"❌ Error: {e}")
        
        elif button_id == "add-channel":
            self.notify("Add Channel: Edit openclaw.json manually or use CLI")
        
        elif button_id == "edit-channel":
            self.notify("Edit Channel: Edit openclaw.json manually")
        
        elif button_id == "remove-channel":
            self.notify("Remove Channel: Edit openclaw.json manually")
        
        elif button_id == "test-channel":
            self.notify("Test Channel: Not implemented yet")
        
        elif button_id == "install-skill":
            self.notify("Install Skill: Use 'clawhub install <skill-name>'")
        
        elif button_id == "update-skill":
            self.notify("Update Skill: Use 'clawhub update <skill-name>'")
        
        elif button_id == "remove-skill":
            self.notify("Remove Skill: Use 'clawhub remove <skill-name>'")


def main():
    app = ClawAPITUI()
    app.run()


if __name__ == "__main__":
    main()
