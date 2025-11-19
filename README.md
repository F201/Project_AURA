# Project AURA (Advanced Universal Responsive Avatar)

*AURA* is an open-source interactive AI Avatar project developed by the **Advanced Software Engineering (ASE) Laboratory**. Inspired by AI VTubers, AURA serves as a virtual assistant capable of answering questions, managing lab information, and providing conversational support via a web portal.

## 🚀 Features

### Conversational Core

- Powered by LLMs (OpenAI/Local) with LangChain

- Semi real-time interactive chatting

- RAG Knowledge Base

- Aware of ASE Lab’s history, projects, and members

- Uses internal documents through vector-based retrieval

- Text-to-Speech (TTS) and Speech-to-Text (STT)

- Generates natural, human-like audio responses

### Dashboard

React-based dashboard for configuration and monitoring

## 🛠️ Tech Stack

- Backend: Python, FastAPI, LangChain, ChromaDB
- Frontend: React, TailwindCSS
- Integrations: OpenAI / Gemini / Local LLMs, TTS & STT Service

## ⚡ Quick Start

### Prerequisites

- Docker & Docker Compose

### Installation

1. Clone the repository:
```bash
git clone https://github.com/ASE-Lab/project-aura.git
cd project-aura
```

2. Copy the environment file and fill in your API Keys then do:
```bash
cp .env.example .env
```

3. Run with docker:
```bash
Run with Docker
docker-compose up --build
```

4. Access:

- Control Panel: http://localhost:3000

- API Docs: http://localhost:8000/docs

## 🤝 Contribution

We follow a standard open-source contribution workflow!

1. Fork the repository.

2. Create a Branch for your feature (git checkout -b feat/add-new-rag-source).

3. Commit your changes.

4. Push to the branch.

5. Open a Pull Request.

See CONTRIBUTING.md for detailed instructions.

## 🗺️ Roadmap

Check our GitHub Projects Board for the latest tasks. (Note: Avatar/VTube integration is slated for a future phase).

## 📜 License

Distributed under the MIT License. See LICENSE for more information.

<p align="center">
Built with ❤️ by the ASE Lab Members
</p>