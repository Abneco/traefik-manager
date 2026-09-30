<script setup>
import { withBase } from 'vitepress'
import TiltIn from './TiltIn.vue'

const sections = [
  {
    kicker: 'Dashboard',
    title: 'Every route becomes a launchable app',
    desc: 'Routes are grouped into categories with live health on every card and a second line only when something is wrong. Switch to the icon grid and the dashboard turns into an app launcher for your whole homelab.',
    img: 'dashboard-icons',
    link: '/tab-dashboard',
  },
  {
    kicker: 'Routes',
    title: 'Add a route in seconds, not in YAML',
    desc: 'Card and list views over every router from every provider, with the stat panel and entry points above. A slide-in form handles domains, backends, load balancing, entry points and middlewares. HTTP, TCP and UDP each get exactly the fields that apply.',
    img: 'routes-cards',
    link: '/tab-routes',
  },
  {
    kicker: 'Middlewares',
    title: 'Wizards that know every config shape',
    desc: '30 guided forms for every common middleware type, from Basic Auth to OIDC to rate limiting, plus one-click presets that attach the right stack to a route.',
    img: 'middlewares-add',
    link: '/tab-middlewares',
  },
  {
    kicker: 'Services',
    title: 'Build a backend pool without touching a route',
    desc: 'Create a load balancer, or a weighted, mirroring or failover service, from raw addresses and other services in any mix. Services written by hand stay read only until you take them over, which records ownership without rewriting the file.',
    img: 'services-add',
    link: '/tab-services',
  },
  {
    kicker: 'Route Map',
    title: 'Follow a request end to end',
    desc: 'The full path of every request, entry point to router to middleware to backend, drawn as a live diagram.',
    img: 'route-map',
    link: '/tab-routemap',
  },
  {
    kicker: 'Access Logs',
    title: 'Know who is hitting your proxy',
    desc: 'Access log analytics with real client IPs, status breakdowns, top routes, and a world map of where your traffic actually comes from.',
    img: 'logs',
    link: '/tab-logs',
  },
  {
    kicker: 'CrowdSec',
    title: 'See what got blocked, and why',
    desc: 'Live CrowdSec decisions inside the UI. Search bans, add your own decisions, and watch attackers bounce before they ever reach an app.',
    img: 'crowdsec',
    link: '/tab-crowdsec',
  },
  {
    kicker: 'Certificates',
    title: 'Expiry tracking straight from acme.json',
    desc: 'Every certificate with days remaining, wildcards, multiple resolvers, and named TLS profiles with mTLS support, assignable per route.',
    img: 'certs',
    link: '/tab-certs',
  },
  {
    kicker: 'Languages',
    title: 'Speaks your language',
    desc: 'The whole interface in 14 languages, from Čeština to 中文, with numbers, dates and notifications to match. Each person picks their own, and Follow system uses the browser language.',
    img: 'multilingual',
    link: '/languages',
  },
  {
    kicker: 'Static Config',
    title: 'traefik.yml as editable cards',
    desc: 'Entry points, certificate resolvers, providers, logging and observability as forms, with raw YAML one click away and a Traefik restart button when you need it.',
    img: 'static-config',
    link: '/static',
  },
]

const extras = [
  {
    title: 'Multi-Server Agent',
    desc: 'Manage unlimited remote Traefik servers from one UI, with live data and remote editing.',
    link: '/agent',
  },
  {
    title: 'Git Backup & Restore',
    desc: 'Auto-push config to GitHub, Gitea, GitLab or Forgejo after every change. Roll back in one click.',
    link: '/git-backup',
  },
  {
    title: 'Real Client IPs',
    desc: 'See the address your visitors actually come from, not your proxy, with a built-in diagnostic.',
    link: '/tab-logs',
  },
  {
    title: 'Security Built In',
    desc: 'bcrypt logins, TOTP 2FA, OIDC SSO and API keys, all out of the box.',
    link: '/security',
  },
  {
    title: 'tm CLI',
    desc: 'Install the whole stack, add an agent, reset a password or switch to the beta channel from one command.',
    link: '/tm-cli',
  },
  {
    title: 'TLS Options',
    desc: 'Named TLS profiles with minimum versions, cipher suites and mTLS, assignable per route.',
    link: '/tab-tls-options',
  },
  {
    title: 'Plugins',
    desc: 'Browse, install and configure Traefik plugins without leaving the UI.',
    link: '/tab-plugins',
  },
  {
    title: 'Notification Webhooks',
    desc: 'Discord, Slack, ntfy, Gotify, Pushover, Pushbullet, Telegram or your phone, whenever your config changes.',
    link: '/webhooks',
  },
]

const phones = ['mobile-overview', 'mobile-routes', 'mobile-logs']
</script>

<template>
  <section id="features" class="hs-wrap">
    <div class="hs-head">
      <h2 class="hs-heading">Features</h2>
      <p class="hs-sub">Everything you need to run Traefik, without touching YAML.</p>
    </div>

    <div
      v-for="(s, i) in sections"
      :key="s.kicker"
      class="hs-row"
      :class="{ 'hs-row-flip': i % 2 === 1 }"
    >
      <div class="hs-copy">
        <span class="hs-kicker">{{ s.kicker }}</span>
        <h3 class="hs-title">{{ s.title }}</h3>
        <p class="hs-desc">{{ s.desc }}</p>
        <a class="hs-link" :href="withBase(s.link)">Explore {{ s.kicker }} <span class="hs-arrow">&rarr;</span></a>
      </div>
      <div class="hs-shot">
        <TiltIn :angle="8" :lift="44" :from-scale="0.96" :fade="0">
          <img class="screenshot light-only" :src="withBase(`/images/light-${s.img}.png`)" :alt="s.title" loading="lazy" />
          <img class="screenshot dark-only" :src="withBase(`/images/dark-${s.img}.png`)" :alt="s.title" loading="lazy" />
        </TiltIn>
      </div>
    </div>

    <div class="hs-extras">
      <span class="hs-kicker">More in the box</span>
      <h3 class="hs-title">It keeps going</h3>
      <div class="hs-extras-grid">
        <a v-for="e in extras" :key="e.title" class="hs-extra" :href="withBase(e.link)">
          <span class="hs-extra-title">{{ e.title }}</span>
          <span class="hs-extra-desc">{{ e.desc }}</span>
        </a>
      </div>
    </div>

    <div class="hs-mobile">
      <span class="hs-kicker">Android App</span>
      <h3 class="hs-title">Take it with you</h3>
      <p class="hs-desc hs-mobile-desc">A native mobile app for the couch and the commute. Routes, middlewares, logs, CrowdSec and backups from your phone or tablet, in the same light and dark themes.</p>
      <TiltIn :angle="8" :lift="44" :from-scale="0.96" :fade="0">
        <div class="hs-phones">
          <div v-for="p in phones" :key="p" class="hs-phone">
            <div class="hs-phone-screen">
              <img :src="withBase(`/images/light-${p}.png`)" alt="Traefik Manager mobile app" class="light-only" loading="lazy" />
              <img :src="withBase(`/images/dark-${p}.png`)" alt="Traefik Manager mobile app" class="dark-only" loading="lazy" />
              <div class="hs-phone-punch" />
            </div>
          </div>
        </div>
      </TiltIn>
      <a class="hs-link" :href="withBase('/mobile')">Get the mobile app <span class="hs-arrow">&rarr;</span></a>
    </div>
  </section>
</template>

<style scoped>
.hs-wrap {
  max-width: 1152px;
  margin: 0 auto;
  padding: 48px 24px 24px;
  scroll-margin-top: 84px;
}

.hs-head {
  text-align: center;
  max-width: 640px;
  margin: 0 auto 72px;
}

.hs-heading {
  font-size: 32px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--vp-c-text-1);
  margin: 0 0 12px;
  border: none;
  padding: 0;
}

.hs-sub {
  font-size: 15px;
  color: var(--vp-c-text-2);
  line-height: 1.6;
  margin: 0;
}

.hs-row {
  display: grid;
  grid-template-columns: 5fr 7fr;
  gap: 48px;
  align-items: center;
  margin-bottom: 88px;
}

.hs-row-flip .hs-copy {
  order: 2;
}

.hs-row-flip .hs-shot {
  order: 1;
}

.hs-kicker {
  display: inline-block;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--vp-c-brand-1);
  background: var(--vp-c-brand-soft);
  border-radius: 20px;
  padding: 3px 12px;
  margin-bottom: 14px;
}

.hs-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.01em;
  line-height: 1.25;
  color: var(--vp-c-text-1);
  margin: 0 0 12px;
  border: none;
  padding: 0;
}

.hs-desc {
  font-size: 15px;
  line-height: 1.65;
  color: var(--vp-c-text-2);
  margin: 0 0 16px;
}

.hs-link {
  font-size: 14px;
  font-weight: 500;
  color: var(--vp-c-brand-1);
  text-decoration: none;
}

.hs-link:hover {
  text-decoration: underline;
}

.hs-arrow {
  display: inline-block;
  transition: transform 0.15s;
}

.hs-link:hover .hs-arrow {
  transform: translateX(3px);
}

.hs-shot img.screenshot {
  margin: 0;
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.12);
}

.dark .hs-shot img.screenshot {
  box-shadow: 0 18px 44px rgba(0, 0, 0, 0.4);
}

.hs-extras {
  text-align: center;
  margin-bottom: 88px;
}

.hs-extras-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-top: 20px;
  text-align: left;
}

.hs-extra {
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 18px;
  text-decoration: none;
  transition: border-color 0.2s;
}

.hs-extra:hover {
  border-color: var(--vp-c-brand-1);
}

.hs-extra-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--vp-c-text-1);
  line-height: 1.3;
}

.hs-extra-desc {
  font-size: 12.5px;
  color: var(--vp-c-text-2);
  line-height: 1.5;
}

.hs-mobile {
  text-align: center;
  padding-top: 24px;
}

.hs-mobile-desc {
  max-width: 560px;
  margin: 0 auto 32px;
}

.hs-phones {
  display: flex;
  justify-content: center;
  align-items: flex-end;
  gap: 24px;
  margin-bottom: 28px;
}

.hs-phone {
  width: 180px;
  background: #16191d;
  border-radius: 26px;
  padding: 6px;
  box-shadow: 0 20px 48px rgba(0, 0, 0, 0.22);
}

.dark .hs-phone {
  box-shadow: 0 22px 54px rgba(0, 0, 0, 0.55);
}

.hs-phone:nth-child(2) {
  width: 200px;
}

.hs-phone-screen {
  border-radius: 21px;
  overflow: hidden;
  aspect-ratio: 864 / 1891;
  position: relative;
}

.hs-phone-screen img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: top;
  display: block;
}

.hs-phone-punch {
  position: absolute;
  top: 9px;
  left: 50%;
  transform: translateX(-50%);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #05070a;
}

.light-only,
.dark-only {
  display: block;
}

@media (max-width: 960px) {
  .hs-extras-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 840px) {
  .hs-row {
    grid-template-columns: 1fr;
    gap: 24px;
    margin-bottom: 64px;
  }
  .hs-row-flip .hs-copy {
    order: 1;
  }
  .hs-row-flip .hs-shot {
    order: 2;
  }
  .hs-phone:nth-child(3) {
    display: none;
  }
}

@media (max-width: 480px) {
  .hs-extras-grid {
    grid-template-columns: 1fr;
  }
  .hs-phone {
    width: 140px;
  }
  .hs-phone:nth-child(2) {
    width: 150px;
  }
}
</style>
