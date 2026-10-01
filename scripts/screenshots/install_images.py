import os

from PIL import Image

GAP = 12
BACKGROUND = {"dark": (11, 14, 20), "light": (233, 237, 242)}


def language_grid(theme):
    shots = sorted(f for f in os.listdir(f"/new/{theme}") if f.startswith("lang-"))[:4]
    if len(shots) < 4:
        print(f"multilingual: only {len(shots)} language shots for {theme}, skipped")
        return
    w = (1920 - GAP) // 2
    h = round(w * 9 / 16)
    grid = Image.new("RGB", (w * 2 + GAP, h * 2 + GAP), BACKGROUND[theme])
    for i, f in enumerate(shots):
        tile = Image.open(f"/new/{theme}/{f}").convert("RGB").resize((w, h), Image.LANCZOS)
        grid.paste(tile, ((i % 2) * (w + GAP), (i // 2) * (h + GAP)))
    grid.save(f"/img/{theme}-multilingual.png", optimize=True)


copied = 0
for theme in ("dark", "light"):
    language_grid(theme)
    for f in sorted(os.listdir(f"/new/{theme}")):
        if f.startswith("lang-"):
            continue
        im = Image.open(f"/new/{theme}/{f}").convert("RGB")
        im = im.resize((im.width // 2, im.height // 2), Image.LANCZOS)
        im.save(f"/img/{theme}-{f[:-4]}.png", optimize=True)
        copied += 1

CAROUSEL = (
    "dashboard", "dashboard-icons", "dashboard-hover",
    "routes-cards", "routes-list", "routes-add-http", "routes-add-tcp", "routes-add-udp",
    "routes-add-service",
    "middlewares-cards", "middlewares-list", "middlewares-add",
    "services-cards", "services-list", "services-detail", "services-add", "services-edit",
    "route-map", "tls-options", "certs", "certs-select", "certs-remove",
    "logs", "crowdsec", "multilingual",
    "plugins", "plugins-add",
    "static-config",
    "settings-interface", "settings-auth-password", "settings-auth-apikeys",
    "settings-auth-oidc", "settings-backups", "settings-system", "settings-routes",
    "settings-connection", "settings-notifications", "settings-notification-channel",
    "settings-agents",
    "settings-about",
    "setup-welcome", "setup-connection", "setup-self-route", "setup-monitoring",
    "setup-crowdsec", "setup-git-backup", "setup-notifications", "setup-password",
)

for theme in ("dark", "light"):
    frames = []
    for n in CAROUSEL:
        p = f"/img/{theme}-{n}.png"
        if not os.path.exists(p):
            print(f"carousel: missing {theme}-{n}.png, skipped")
            continue
        frames.append(Image.open(p).convert("RGB").resize((1280, 720), Image.LANCZOS))
    frames[0].save(f"/img/readme-carousel-{theme}.gif", save_all=True,
                   append_images=frames[1:], duration=1600, loop=0, optimize=True)

print(f"{copied} screenshots installed, 2 carousel GIFs rebuilt from {len(CAROUSEL)} screens")
