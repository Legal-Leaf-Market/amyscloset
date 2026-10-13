# Crossroads Private Line (`/messaging/`)

Private 1-to-1 texting, voice calls and video calls in the browser. No accounts, no app to install, nothing stored.

## How to use it
1. Open `/messaging/` and tap **Start a new private line**.
2. Pick a display name and a **self-destruct password** (typed twice).
3. Copy the link and send it to the other person privately. They open it, pick their own name and self-destruct password, and you're connected.
4. Text, or tap **Call** / **Video**.
5. **Self-destruct**: tap it, type your password twice. Every message disappears on *both* devices, any call ends, and the link stops opening on those devices.

## How it stays private
- **The key lives only in the link**, after the `#`. Browsers never send that part to any server.
- Texts are encrypted with AES-256-GCM using that key, then sent over WebRTC, which encrypts again (DTLS). Calls use WebRTC's built-in SRTP encryption, and only the verified person in the chat can call.
- Someone who has the room ID but the wrong key is disconnected right away.
- Messages exist only in the open tab's memory. Closing the tab erases them. Nothing goes to a database.
- The self-destruct password is kept as a salted PBKDF2 hash in memory, and only on your device.

## Honest limits
- Anyone who gets the link can join while the line is empty. Share it only with the person you mean.
- The free PeerJS broker (`0.peerjs.com`) introduces the two devices. It sees random IDs and IP addresses, never message content. If a direct connection is impossible, traffic goes through PeerJS's TURN relay, still encrypted.
- Self-destruct can't undo screenshots, or a device that has been modified.
- Two people per line. The first person to open the link holds the line, so the other person can drop out and rejoin with the same link.

## Hosting at crossroadsonnetcode.shop/messaging
This folder is plain static files (`index.html` plus a bundled copy of PeerJS 1.5.4, MIT licensed). Upload the `messaging/` folder to the web root of crossroadsonnetcode.shop. It must be served over **https**, because browsers block the camera and microphone on plain http.

To run your own broker instead of the free one, run a [PeerServer](https://github.com/peers/peerjs-server). Before `peerjs.min.js` loads, set `window.CROSSROADS_BROKER = { host, port, path, secure: true }` and add that host to the page's `connect-src` policy.
