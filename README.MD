![Docker TUI Header](https://github.com/905timur/docker-tui/blob/main/repo-header.svg)

docker-tui is a terminal user interface (TUI) for interacting with Docker containers, built with Textual and the Docker SDK for Python.

## Features
- View running containers
- Inspect container status and metadata
- Live-updating TUI using Textual

# Main Screen
![docker-tui main screen](https://github.com/905timur/docker-tui/blob/main/img/main-screen.png)

# Logging Screen
![docker-tui logging screen](https://github.com/905timur/docker-tui/blob/main/img/logging-screen.png)

## Requirements
- Python 3.10+
- Docker (local socket access)
- Linux or macOS

## Installation

```bash
git clone https://github.com/905timur/docker-tui.git
cd docker-tui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python docker_tui.py
```
## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=905timur/docker-tui&type=date&legend=top-left)](https://www.star-history.com/#905timur/docker-tui&type=date&legend=top-left)
