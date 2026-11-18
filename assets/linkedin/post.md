I’ve started Mage Agents Lab: a personal project to turn what I’ve been learning about AI agents into a useful, local-first assistant.

The first version focuses on three everyday tasks:

• Reviewing two Gmail inboxes and highlighting important messages.
• Collecting AI, agent, framework, and developer news into a daily briefing with source links.
• Preparing email drafts that only send after I review and approve them.

The foundation uses Python, FastAPI, a background worker, SQLite, Gmail OAuth, OpenAI, and Docker Compose. The diagram shows how the pieces fit together today.

This is still the beginning. Next, I want to make the agent layer more reusable and build secure desktop and phone access as the project grows. I’ll share the decisions, mistakes, and improvements along the way.

GitHub: https://github.com/supervipe/Mage-Agents-Lab

#BuildInPublic #AIAgents #Python #FastAPI
