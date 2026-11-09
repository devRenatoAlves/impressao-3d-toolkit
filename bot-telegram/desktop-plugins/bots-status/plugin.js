/**
 * bots-status — always-visible health of the Hermes messaging gateway.
 *
 * A bot configured from the terminal leaves no way to tell whether it is alive
 * without reading gateway.log. This plugin surfaces that state permanently:
 *
 *   - a statusbar chip (dot + platform summary) that is always on screen;
 *   - a side pane with the full breakdown;
 *   - both click through to the app's own Messaging page, which already owns
 *     the enable/disable switch and the gateway restart button. This plugin
 *     deliberately does NOT duplicate those controls: toggling a platform means
 *     writing platforms.<name>.enabled and restarting the gateway, and the
 *     native page does it through the supported REST path.
 *
 * Data comes from bin/status-bots.py, which reads gateway_state.json (the file
 * the gateway itself rewrites on every connection change). The chip uses
 * --quick (~60 ms, no network probe) so polling stays cheap.
 *
 * Plain ESM, loaded uncompiled: UI is jsx() calls, not JSX syntax.
 */

import {
  Button,
  cn,
  haptic,
  host,
  PALETTE_AREA,
  queryClient,
  StatusDot,
  Tip,
  useQuery,
  useQueryClient,
  usePluginI18n
} from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'

const ID = 'bots-status'
// Resolved by the shell at call time: a named profile moves HERMES_HOME, and a
// hardcoded ~/.hermes would read the wrong profile's gateway state.
const SCRIPT = '"${HERMES_HOME:-$HOME/.hermes}/bin/status-bots.py"'

// The chip is cheap to refresh; the full panel probes the printer, so it waits.
const QUICK_INTERVAL_MS = 10_000
const FULL_INTERVAL_MS = 30_000

/** Map the script's colour hint onto the app's semantic StatusDot tones. */
const TONES = { green: 'good', yellow: 'warn', red: 'bad', grey: 'muted' }

/** Per-platform state → tone, so a row reads the same as the chip. */
const STATE_TONES = {
  connected: 'good',
  connecting: 'warn',
  retrying: 'warn',
  degraded: 'warn',
  pending_restart: 'warn',
  error: 'bad',
  disabled: 'muted',
  not_configured: 'muted'
}

/**
 * Run the status script through the gateway and parse its JSON.
 *
 * shell.exec refuses commands its approval layer classifies as dangerous, which
 * is why this plugin never shells out to `systemctl` or `hermes gateway
 * restart` — those are blocked by design. Reading status is allowed.
 */
async function readStatus(flag) {
  const result = await host.request('shell.exec', { command: `python3 ${SCRIPT} ${flag}` })
  const stdout = (result?.stdout || '').trim()
  if (!stdout) {
    throw new Error(result?.stderr?.trim() || `status-bots.py exited ${result?.code}`)
  }
  return JSON.parse(stdout)
}

function useQuickStatus() {
  return useQuery({
    queryKey: [ID, 'quick'],
    queryFn: () => readStatus('--quick'),
    refetchInterval: QUICK_INTERVAL_MS,
    staleTime: QUICK_INTERVAL_MS,
    retry: 1
  })
}

function useFullStatus() {
  return useQuery({
    queryKey: [ID, 'full'],
    queryFn: () => readStatus('--json'),
    refetchInterval: FULL_INTERVAL_MS,
    staleTime: FULL_INTERVAL_MS,
    retry: 1
  })
}

/** Open the app's own Messaging page — where the on/off switch lives. */
function openMessaging(ctx) {
  haptic('tap')
  const ran = ctx.runAction('nav.messaging')
  if (!ran?.ok) host.navigate('/messaging')
}

// ── statusbar chip ────────────────────────────────────────────────────────────

function Chip({ ctx }) {
  const t = usePluginI18n(ID)
  const { data, error } = useQuickStatus()

  const tone = error ? 'bad' : TONES[data?.dot] || 'muted'
  const label = error ? t('chipError') : data?.label || t('chipLoading')
  const detail = error ? String(error.message || error) : data?.detail || ''

  return jsx(Tip, {
    label: `${label}${detail ? ` — ${detail}` : ''}\n${t('chipHint')}`,
    children: jsxs('button', {
      className: cn(
        'inline-flex h-full items-center gap-1.5 px-1.5 text-[0.6875rem] transition-colors',
        'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground'
      ),
      type: 'button',
      onClick: () => openMessaging(ctx),
      children: [
        jsx(StatusDot, { tone }),
        jsx('span', { className: 'max-w-40 truncate', children: label })
      ]
    })
  })
}

// ── side pane ─────────────────────────────────────────────────────────────────

function Row({ name, info, t }) {
  const tone = STATE_TONES[info.state] || 'warn'
  const note = info.error_message || info.last_log_error || ''

  return jsxs('div', {
    className: 'flex flex-col gap-0.5 py-1',
    children: [
      jsxs('div', {
        className: 'flex items-center gap-1.5',
        children: [
          jsx(StatusDot, { tone }),
          jsx('span', { className: 'font-medium', children: name }),
          jsx('span', {
            className: 'text-(--ui-text-tertiary)',
            children: t(`state.${info.state}`) || info.state
          })
        ]
      }),
      note
        ? jsx('div', {
            className: 'pl-3 text-[0.6875rem] break-words text-(--ui-text-quaternary)',
            children: note
          })
        : null
    ]
  })
}

function Pane({ ctx }) {
  const t = usePluginI18n(ID)
  const client = useQueryClient()
  const { data, error, isFetching } = useFullStatus()

  if (error) {
    return jsxs('div', {
      className: 'flex h-full flex-col gap-2 p-3 text-sm',
      children: [
        jsx('div', { className: 'font-medium', children: t('paneTitle') }),
        jsx('div', {
          className: 'text-(--ui-text-tertiary)',
          children: String(error.message || error)
        })
      ]
    })
  }

  const service = data?.service
  const platforms = data?.platforms || {}
  // A platform with no credential and no config block is noise in a 237px pane.
  const rows = Object.entries(platforms)
    .filter(([, info]) => info.state !== 'not_configured')
    .sort(([a], [b]) => a.localeCompare(b))
  const printer = data?.printer

  return jsxs('div', {
    className: 'flex h-full flex-col gap-3 overflow-y-auto p-3 text-xs',
    children: [
      // Gateway
      jsxs('div', {
        className: 'flex flex-col gap-1',
        children: [
          jsxs('div', {
            className: 'flex items-center gap-1.5 text-sm',
            children: [
              jsx(StatusDot, { tone: service?.active ? 'good' : 'bad' }),
              jsx('span', {
                className: 'font-medium',
                children: service?.active ? t('gatewayUp') : t('gatewayDown')
              })
            ]
          }),
          service?.active
            ? jsx('div', {
                className: 'pl-3 text-(--ui-text-tertiary)',
                children: t('gatewayMeta', service.uptime, service.memory_mb)
              })
            : null,
          jsx('div', {
            className: 'pl-3 text-(--ui-text-quaternary)',
            children: service?.autostart ? t('bootOn') : t('bootOff')
          })
        ]
      }),

      // Platforms
      jsxs('div', {
        className: 'flex flex-col',
        children: [
          jsx('div', {
            className: 'pb-1 text-[0.6875rem] uppercase tracking-wide text-(--ui-text-quaternary)',
            children: t('platforms')
          }),
          ...(rows.length
            ? rows.map(([name, info]) => jsx(Row, { name, info, t }, name))
            : [jsx('div', { className: 'text-(--ui-text-tertiary)', children: t('noPlatforms') })])
        ]
      }),

      // Printer (only when the .env actually names one)
      printer?.configured
        ? jsxs('div', {
            className: 'flex items-center gap-1.5',
            children: [
              jsx(StatusDot, { tone: printer.reachable ? 'good' : 'bad' }),
              jsx('span', {
                className: 'text-(--ui-text-tertiary)',
                children: t('printer', printer.host, printer.reachable)
              })
            ]
          })
        : null,

      // Actions. The on/off switch itself lives on the native Messaging page.
      jsxs('div', {
        className: 'mt-auto flex flex-col gap-1.5 border-t border-(--ui-stroke-secondary) pt-2',
        children: [
          jsx(Button, {
            size: 'sm',
            variant: 'secondary',
            onClick: () => openMessaging(ctx),
            children: t('openMessaging')
          }),
          jsx(Button, {
            size: 'sm',
            variant: 'ghost',
            disabled: isFetching,
            onClick: () => {
              haptic('tap')
              void client.invalidateQueries({ queryKey: [ID] })
            },
            children: isFetching ? t('refreshing') : t('refresh')
          }),
          jsx('div', {
            className: 'text-[0.625rem] leading-snug text-(--ui-text-quaternary)',
            children: t('toggleHint')
          })
        ]
      })
    ]
  })
}

export default {
  id: ID,
  name: 'Bots Status',
  register(ctx) {
    // The desktop app ships no pt/pt-BR locale (en, es, fr, de, ja, ru, zh, ar),
    // and this install runs display.language: en. Registering the Portuguese
    // copy under BOTH keys means it shows today on `en` and keeps working if a
    // pt locale is ever added or the language is switched.
    const pt = {
      chipLoading: 'lendo bots…',
      chipError: 'status indisponivel',
      chipHint: 'Clique para abrir Messaging (ligar/desligar)',
      paneTitle: 'Status dos bots',
      gatewayUp: 'Gateway rodando',
      gatewayDown: 'Gateway parado',
      gatewayMeta: (uptime, mb) => `de pé há ${uptime}${mb ? ` · ${mb} MB` : ''}`,
      bootOn: 'sobe sozinho no boot',
      bootOff: 'NÃO sobe no boot',
      platforms: 'Plataformas',
      noPlatforms: 'Nenhuma plataforma configurada',
      printer: (printerHost, ok) =>
        `Impressora ${printerHost} — ${ok ? 'alcançável' : 'fora de alcance'}`,
      openMessaging: 'Abrir Messaging',
      refresh: 'Atualizar',
      refreshing: 'Atualizando…',
      toggleHint: 'Ligar/desligar um bot: Messaging → switch da plataforma → Reiniciar gateway.',
      'state.connected': 'conectado',
      'state.connecting': 'conectando',
      'state.retrying': 'reconectando',
      'state.degraded': 'degradado',
      'state.pending_restart': 'aguardando reinício',
      'state.disabled': 'desligado',
      'state.not_configured': 'não configurada',
      'state.error': 'com erro'
    }

    ctx.i18n.register({ en: pt, pt })

    ctx.register({
      id: 'chip',
      area: 'statusBar.right',
      order: 120,
      render: () => jsx(Chip, { ctx })
    })

    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'bots',
      data: { placement: 'right', width: '237px' },
      render: () => jsx(Pane, { ctx })
    })

    ctx.register({
      id: 'open-messaging',
      area: PALETTE_AREA,
      data: {
        id: 'bots-status.openMessaging',
        label: 'Bots: abrir Messaging',
        keywords: ['bot', 'telegram', 'gateway', 'mensageria', 'status'],
        run: () => openMessaging(ctx)
      }
    })

    // The gateway broadcasts this whenever it rewrites gateway_state.json, so a
    // connect/disconnect shows up without waiting for the next poll.
    return host.onEvent('platforms.changed', () => {
      void queryClient.invalidateQueries({ queryKey: [ID] })
    })
  }
}
