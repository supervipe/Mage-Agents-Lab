# Private access from Canada with Nord Meshnet

The API and worker stay on the Linux laptop in Brazil. The Windows and Ubuntu computers in Canada connect over Nord Meshnet. No domain, router port forwarding, or cloud deployment is needed. Meshnet itself is free; OpenAI usage and the laptop's electricity/internet are separate costs.

## Brazil laptop (Linux host)

1. Install NordVPN for your Linux distribution using [Nord's Linux guide](https://meshnet.nordvpn.com/getting-started/how-to-start-using-meshnet/using-meshnet-on-linux). Sign in to the Nord account you use on your other devices and enable Meshnet:

   ```bash
   nordvpn login
   nordvpn set meshnet on
   nordvpn meshnet peer list
   ```

2. Find **this laptop's** Meshnet IP and Nord name in the Nord app or Nord Account Meshnet device page. You can also see the Brazil device's details from the Windows Nord app after both devices are linked. Add these two values to the ignored `.env` file in this project:

   ```dotenv
   MESHNET_BIND_IP=100.x.y.z
   MESHNET_HOST=your-brazil-device.nord
   ```

   Use the exact assigned IP and name; the values above are examples. Do not put Gmail addresses, tokens, or passwords in tracked files. The existing `GMAIL_ACCOUNTS` and `OPENAI_API_KEY` stay in `.env`.

3. Create the two ignored secret files. The dashboard script prompts for a password of at least 16 characters and stores only its password hash and a session signing key:

   ```bash
   python3 scripts/init_linux_secrets.py
   python3 scripts/init_dashboard_auth.py
   ```

   Keep `.secrets/` private and back it up securely. If you replace `dashboard_auth`, existing browser sessions stop working.

4. With Meshnet running, build and start the application using both Compose files:

   ```bash
   docker compose -f compose.yaml -f compose.meshnet.yaml build
   docker compose -f compose.yaml -f compose.meshnet.yaml up -d api worker
   docker compose -f compose.yaml -f compose.meshnet.yaml ps
   curl http://127.0.0.1:8000/health
   ```

   The normal Compose file keeps `127.0.0.1:8000` for local use. The override adds port 8000 on **only the Meshnet IP**. Do not replace either binding with `0.0.0.0` and do not forward this port on the home router. The app requires a dashboard password; Meshnet provides the encrypted connection between devices.

5. In Nord Meshnet's device permissions, allow **remote access to this laptop** from only the Windows and Ubuntu devices you use. Traffic routing and access to the Brazil home LAN are unnecessary for this application. Keep Linux awake when the lid closes and enable Docker to start at boot.

6. To start the services automatically after the Meshnet IP appears on reboot, install the included per-user systemd unit and keep user services running when you sign out:

   ```bash
   python3 scripts/install_meshnet_autostart.py
   systemctl --user daemon-reload
   systemctl --user enable --now mage-agents-lab.service
   sudo loginctl enable-linger "$USER"
   ```

   The helper waits up to three minutes for `MESHNET_BIND_IP` and retries if it is not available yet. After a reboot, check `systemctl --user status mage-agents-lab.service` and `docker compose -f compose.yaml -f compose.meshnet.yaml ps`. Docker's `restart: unless-stopped` handles ordinary container restarts.

## Canada computer (Windows)

1. Open the NordVPN app, sign in to the same Nord account, and turn on **Devices in Meshnet**. Leave your regular NordVPN connection on. [Nord's Windows Meshnet steps](https://meshnet.nordvpn.com/getting-started/how-to-start-using-meshnet/using-meshnet-on-windows) show the current controls.
2. Confirm the Brazil laptop appears as an online personal device. Copy its Nord name. In PowerShell, test the private API:

   ```powershell
   curl.exe http://your-brazil-device.nord:8000/health
   ```

3. Open `http://your-brazil-device.nord:8000/` in your browser and sign in with the dashboard password you chose on the Brazil laptop. A future Windows desktop frontend will use the same private address and sign-in API. Keep the NordVPN connection active during the test, then reconnect it and confirm the page still loads.

## Other Canada computer (Ubuntu)

1. Install the NordVPN Linux app, sign in to the **same Nord account**, and enable Meshnet:

   ```bash
   nordvpn login
   nordvpn set meshnet on
   nordvpn meshnet peer list
   ```

2. Confirm the Brazil device is listed and test it:

   ```bash
   curl http://your-brazil-device.nord:8000/health
   ```

3. Open `http://your-brazil-device.nord:8000/` in a browser and sign in. The later Ubuntu frontend can use the same address. Meshnet also works when your regular NordVPN connection is active; test that combination on this computer if you use it there.

## If the connection fails

- First check that all devices show as online in Meshnet, that the Brazil laptop is awake, and that the `api` container is healthy. Test `http://127.0.0.1:8000/health` on the Brazil laptop.
- If the Brazil device responds to a Meshnet ping but port 8000 does not respond, check that `MESHNET_BIND_IP` matches the laptop's **current** Meshnet IP, that the override was included in the Compose command, and that the Linux firewall permits TCP 8000 on the Meshnet interface only.
- Nord [documents a Docker-specific Meshnet restriction](https://meshnet.nordvpn.com/troubleshooting/linux). If host-port access is blocked, investigate that restriction before granting broader local-network permission, which also exposes more of the Brazil network to that peer.
- If `.nord` name resolution fails, try the Brazil laptop's Meshnet IP in the URL. `MESHNET_BIND_IP` is already allowed by the API's trusted-host setting.
- The Google OAuth app remains in Testing. Gmail consent may need renewal about every seven days; fixing remote access does not remove that limit. The current OAuth callback expects a browser on the Brazil laptop.

HTTP is used **inside** Meshnet's encrypted private connection. Do not use this address outside Meshnet or publish the port to the public internet. For future access without Meshnet, add HTTPS and reassess authentication before exposing the app.
