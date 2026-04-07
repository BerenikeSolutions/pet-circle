/**
 * PetCircle — Dashboard Snapshot Card
 *
 * Next.js Edge Function that generates a 600×315 PNG image card for a pet's
 * dashboard. Called by the WhatsApp onboarding flow after profile setup is
 * complete — the image is sent as a WhatsApp image message before the text
 * closing summary.
 *
 * Usage: GET /api/og?token=<dashboard_token>
 *
 * The route calls the backend GET /dashboard/{token} endpoint to fetch live,
 * fully-populated pet data. The rendered card shows real values — not a
 * loading skeleton — because data is fetched server-side before rendering.
 *
 * Falls back to a generic "profile ready" card if the backend is unreachable.
 */

import { ImageResponse } from 'next/og'
import { NextRequest } from 'next/server'

export const runtime = 'edge'

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.API_URL ??
  'http://localhost:8000'

/** Status label → short display text */
function statusLabel(status: string, lastDone?: string | null, nextDue?: string | null): string {
  // Align with dashboard reminders/care-plan behavior for missing history.
  if (!lastDone && !nextDue) return '✗ Overdue'
  switch (status) {
    case 'up_to_date': return '✓ Up to date'
    case 'upcoming':   return '⚠ Due soon'
    case 'overdue':    return '✗ Overdue'
    default:           return status ?? ''
  }
}

/** Pick up to N items from arr, return joined string or fallback */
function summarise(items: string[], max: number, fallback: string): string {
  const picked = items.filter(Boolean).slice(0, max)
  return picked.length ? picked.join('  ·  ') : fallback
}

export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get('token')
  if (!token) {
    return new Response('Missing token', { status: 400 })
  }

  // --- Fetch live dashboard data ---
  let data: any = null
  try {
    const res = await fetch(`${API_BASE}/dashboard/${token}`, {
      // Cache at the edge for 60 s — data doesn't change that fast
      next: { revalidate: 60 },
    })
    if (res.ok) data = await res.json()
  } catch (_) {
    /* fall through — render fallback card */
  }

  const pet      = data?.pet ?? {}
  const records: any[] = data?.preventive_records ?? []

  const name     = (pet.name as string)   || 'Your pet'
  const breed    = (pet.breed as string)  || ''
  const gender   = (pet.gender as string) || ''
  const photoUrl = (pet.photo_url as string | null | undefined) ?? ''

  // --- Build section summaries from preventive_records ---

  // HEALTH — vaccines, deworming, flea/tick from health circle
  const healthRecords = records.filter((r) => r.circle === 'health')
  const healthLines = healthRecords.slice(0, 3).map(
    (r) => `${r.item_name}: ${statusLabel(r.status, r.last_done_date, r.next_due_date)}`
  )
  const healthStr = summarise(healthLines, 3, 'Not recorded')

  // NUTRITION — records in the nutrition circle
  const nutritionRecords = records.filter((r) => r.circle === 'nutrition')
  const nutritionLines = nutritionRecords.slice(0, 2).map(
    (r) => `${r.item_name}: ${statusLabel(r.status, r.last_done_date, r.next_due_date)}`
  )
  const nutritionStr = summarise(nutritionLines, 2, 'Not recorded')

  // HYGIENE — records in the hygiene circle
  const hygieneRecords = records.filter((r) => r.circle === 'hygiene')
  const hygieneLines = hygieneRecords.slice(0, 2).map(
    (r) => `${r.item_name}: ${statusLabel(r.status, r.last_done_date, r.next_due_date)}`
  )
  const hygieneStr = summarise(hygieneLines, 2, 'Not recorded')

  const subtitle = [breed, gender].filter(Boolean).join(' · ')

  // --- Render ---
  return new ImageResponse(
    (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          width: '100%',
          height: '100%',
          backgroundColor: '#FFF8F5',
          fontFamily: 'system-ui, sans-serif',
        }}
      >
        {/* ── Header ── */}
        <div
          style={{
            display: 'flex',
            backgroundColor: '#D44800',
            padding: '18px 28px',
            alignItems: 'center',
            gap: '16px',
          }}
        >
          {/* Pet photo or paw fallback */}
          {photoUrl ? (
            <img
              src={photoUrl}
              width={70}
              height={70}
              style={{
                borderRadius: '50%',
                objectFit: 'cover',
                border: '2px solid rgba(255,255,255,0.6)',
              }}
            />
          ) : (
            <div
              style={{
                width: 70,
                height: 70,
                borderRadius: '50%',
                backgroundColor: '#FF7A40',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 32,
                color: '#fff',
              }}
            >
              🐾
            </div>
          )}

          {/* Name + subtitle */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span
              style={{
                color: '#fff',
                fontSize: 30,
                fontWeight: 700,
                lineHeight: 1,
              }}
            >
              {name}
            </span>
            {subtitle && (
              <span style={{ color: '#FFD0B5', fontSize: 15 }}>{subtitle}</span>
            )}
          </div>

          {/* "Profile ready" badge */}
          <div
            style={{
              marginLeft: 'auto',
              backgroundColor: 'rgba(255,255,255,0.18)',
              borderRadius: 20,
              padding: '4px 14px',
              display: 'flex',
            }}
          >
            <span style={{ color: '#fff', fontSize: 13, fontWeight: 600 }}>
              Profile ready ✓
            </span>
          </div>
        </div>

        {/* ── Body ── */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            padding: '18px 28px',
            gap: 14,
            flex: 1,
          }}
        >
          {(
            [
              ['HEALTH',    healthStr],
              ['NUTRITION', nutritionStr],
              ['HYGIENE',   hygieneStr],
            ] as const
          ).map(([label, value]) => (
            <div
              key={label}
              style={{ display: 'flex', flexDirection: 'column', gap: 3 }}
            >
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: '#D44800',
                  letterSpacing: '1.5px',
                  textTransform: 'uppercase',
                }}
              >
                {label}
              </span>
              <span style={{ fontSize: 14, color: '#333', lineHeight: 1.4 }}>
                {value}
              </span>
            </div>
          ))}
        </div>

        {/* ── Footer ── */}
        <div
          style={{
            display: 'flex',
            padding: '10px 28px',
            backgroundColor: '#FFF0E8',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderTop: '1px solid #FFD9C4',
          }}
        >
          <span style={{ fontSize: 12, color: '#999' }}>PetCircle</span>
          <span style={{ fontSize: 12, color: '#D44800', fontWeight: 600 }}>
            View full dashboard →
          </span>
        </div>
      </div>
    ),
    { width: 600, height: 315 }
  )
}
