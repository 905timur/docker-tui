# docker-tui

A terminal user interface (TUI) for interacting with Docker containers, built with Textual and the Docker SDK for Python.

## Features
- View running containers
- Inspect container status and metadata
- Live-updating TUI using Textual

## Requirements
- Python 3.10+
- Docker (local socket access)
- Linux or macOS

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/docker-tui.git
cd docker-tui
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python docker_tui.py
