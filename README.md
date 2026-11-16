# Naify

**Turn Markdown image URLs into on-demand NovelAI images.**

Naify is a local FastAPI server that accepts an image prompt through a URL, requests an image from the NovelAI API, and returns the generated image as WebP. It is designed to work with Markdown image syntax such as `![](URL)`.

> **Status:** v0.6.0dev — pre-release development. Windows executable packaging has been tested locally; a public binary release is not yet available. Android currently requires a manual Python/Termux setup. An Android APK is planned for a later version.

## Features

- Generate images through NovelAI Diffusion models supported by the configured API.
- Use URLs directly in Markdown image tags.
- Cache generated WebP images using a SHA-256 hash of the requested prompt.
- Queue image generation requests to avoid concurrent NovelAI generation calls.
- Limit the cache by total size and image count, with automatic cleanup.
- Configure generation options, base/negative prompts, and an API key through a local web manager.
- Browse and clear cached images in the web manager.
- Shut down the server safely after active generation requests finish.

## How it works

1. A Markdown viewer requests `http://127.0.0.1:8000/get_image?prompt=...`.
2. Naify checks the cache for the SHA-256 hash of the prompt.
3. If cached, the WebP image is returned immediately.
4. Otherwise, the request is queued, sent to NovelAI, cached, and returned as a WebP image.

**Note:** The current cache key is based on the URL prompt alone. Changing generation settings or the base/negative prompts does not automatically invalidate an existing cached image with the same URL prompt.

## Windows

### Standalone executable

When a Windows build is published, download `Naify.exe` from the [Releases](https://github.com/lychan0706/Naify/releases) page and run it.

The executable bundles Python and its dependencies: users do **not** need to install Python or pip.

The server starts on `http://127.0.0.1:8000/`, and Naify opens the web manager in your default browser. Enter your own NovelAI API key and adjust the generation settings before making image requests.

The API key and cache are stored outside the executable so they can persist across application updates.

### Run from source

Requires Python 3.13 and an internet connection for image generation.

```powershell
git clone https://github.com/lychan0706/Naify.git
cd Naify
python -m pip install -r requirements.txt
python main.py
```

Open `http://127.0.0.1:8000/` if the web manager does not open automatically.

## Using Naify in Markdown

After starting Naify and configuring your NovelAI API key, add an image URL:

```markdown
![Generated image](http://127.0.0.1:8000/get_image?prompt=1girl%2C%20blue%20eyes)
```

The `prompt` query parameter contains the image-specific prompt. URL-encode special characters and spaces when constructing the URL.

The server must be running when the Markdown viewer fetches the image. Because `127.0.0.1` refers to the **device running the viewer**, a viewer on another device cannot access your PC's local Naify server through this URL.

The same prompt will normally return the cached image until that cache entry is removed.

## Data storage

| Environment | User data directory |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Naify\` |
| Termux / other POSIX environments | `~/.local/share/naify/` |

The directory contains:

- `config.json` — generation and cache settings.
- `secrets.json` — NovelAI API key.
- `cache/` — generated WebP files.

**Keep `secrets.json` private.** It contains the API key in plain text. Do not commit or share it.

Microsoft Store versions of Python may transparently redirect AppData writes into the Python package's private `LocalCache` directory. A standalone, non-packaged Windows executable does not use that Python-specific redirection.

## Android / Termux

Naify has been run through Python in Termux, but there is currently no published Android APK or automated installer. For manual use, install Python and the project dependencies in Termux and run `python main.py` from the repository directory.

Android APK packaging and Android-specific app lifecycle/background execution support are future work.

## Requirements and limitations

- A valid NovelAI API key is required to generate new images.
- Image generation uses NovelAI's service and may consume account credits/Anlas according to your account and settings.
- The server currently binds to `127.0.0.1:8000` only.
- Another application using port 8000 will prevent the server from starting normally.
- Windows may show a SmartScreen warning for an unsigned executable.
- Naify is an independent project and is not affiliated with NovelAI.

## Development

Core technologies: Python, FastAPI, Uvicorn, httpx, Pydantic, HTML, CSS, and JavaScript.

To create a Windows one-file build using PyInstaller:

```powershell
python -m pip install pyinstaller
python -m PyInstaller --onefile --add-data "web;web" --name Naify main.py
```

The resulting executable is placed in `dist/Naify.exe`. Build on Windows for a Windows executable. Test the executable before distributing it.

## License

No license file has been published yet. Until a license is added, this repository does not grant general permission to redistribute or modify the source code.
