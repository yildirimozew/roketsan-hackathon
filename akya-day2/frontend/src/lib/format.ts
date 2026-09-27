// Display formatting only. No domain math here.
import { t } from '@/i18n'

/** Turkish display name for a zone/base name from the data; unknown names pass through. */
export const placeName = (name: string): string => t.places[name] ?? name

const trNumber = (value: number, digits: number) =>
  value.toLocaleString('tr-TR', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const formatKm = (meters: number | null | undefined): string =>
  meters == null ? '—' : `${trNumber(meters / 1000, 2)} km`

export const formatMeters = (meters: number | null | undefined): string =>
  meters == null ? '—' : `${trNumber(meters, meters < 10 ? 1 : 0)} m`

export const formatSpeed = (ms: number | null | undefined): string =>
  ms == null ? '—' : `${trNumber(ms, 1)} m/s`

export const formatCoord = (value: number, digits = 5): string => value.toFixed(digits)

export const formatPercent = (ratio: number): string => `${Math.round(ratio * 100)}%`

export const formatMs = (ms: number | null | undefined): string =>
  ms == null ? '' : ms < 1000 ? `${ms} ms` : `${trNumber(ms / 1000, 1)} s`
