import { useCallback, useEffect, useRef, useState } from 'react'
import type { Pt } from '@/lib/fieldMap'

interface View {
  cx: number
  cy: number
  w: number // visible width in meters
}

const MIN_W = 150
const MAX_W = 40_000
const FLY_MS = 350

/** Width in meters that shows a circle of `radiusM` around the origin in a w×h pixel box. */
const fitWidth = (radiusM: number, w: number, h: number) => 2 * radiusM * Math.max(1, w / h)

/** Pan (drag) and zoom (wheel, around the cursor) for an SVG whose units are meters.
 *  The first measured size fits a circle of `fitRadiusM` around the origin. */
export function useMapViewport(fitRadiusM: number) {
  const ref = useRef<SVGSVGElement>(null)
  const [size, setSize] = useState({ w: 1, h: 1 })
  const [view, setView] = useState<View>({ cx: 0, cy: 0, w: 2 * fitRadiusM })
  const fitted = useRef(false)
  const viewRef = useRef(view)
  useEffect(() => {
    viewRef.current = view
  }, [view])
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null)
  const dragged = useRef(false)
  const anim = useRef(0)

  const h = view.w * (size.h / size.w)
  const mpp = view.w / size.w // meters per screen pixel, for constant-size markers

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const measure = (w: number, h: number) => {
      setSize({ w: w || 1, h: h || 1 })
      if (!fitted.current && w > 1 && h > 1) {
        fitted.current = true
        setView({ cx: 0, cy: 0, w: fitWidth(fitRadiusM, w, h) })
      }
    }
    // Measure once now: until the observer fires the size is 1 px, which would draw every
    // constant-size marker (mpp = meters per 1 px) across the whole map for a frame.
    const box = el.getBoundingClientRect()
    measure(box.width, box.height)
    const ro = new ResizeObserver(([entry]) => {
      if (entry) measure(entry.contentRect.width, entry.contentRect.height)
    })
    ro.observe(el)
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      cancelAnimationFrame(anim.current)
      const r = el.getBoundingClientRect()
      const v = viewRef.current
      const vh = v.w * (r.height / r.width)
      const px = v.cx - v.w / 2 + ((e.clientX - r.left) / r.width) * v.w
      const py = v.cy - vh / 2 + ((e.clientY - r.top) / r.height) * vh
      const w = Math.max(MIN_W, Math.min(MAX_W, v.w * (e.deltaY > 0 ? 1.2 : 1 / 1.2)))
      const k = w / v.w
      setView({ cx: px + (v.cx - px) * k, cy: py + (v.cy - py) * k, w })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => {
      ro.disconnect()
      el.removeEventListener('wheel', onWheel)
    }
  }, [fitRadiusM])

  const flyTo = useCallback((p: Pt, w?: number) => {
    cancelAnimationFrame(anim.current)
    const from = viewRef.current
    const to = { cx: p.x, cy: p.y, w: w ?? from.w }
    const t0 = performance.now()
    const step = (now: number) => {
      const k = Math.min(1, (now - t0) / FLY_MS)
      const e = 1 - (1 - k) ** 3
      setView({
        cx: from.cx + (to.cx - from.cx) * e,
        cy: from.cy + (to.cy - from.cy) * e,
        w: from.w + (to.w - from.w) * e,
      })
      if (k < 1) anim.current = requestAnimationFrame(step)
    }
    anim.current = requestAnimationFrame(step)
  }, [])

  const fit = useCallback(
    () => flyTo({ x: 0, y: 0 }, fitWidth(fitRadiusM, size.w, size.h)),
    [flyTo, fitRadiusM, size],
  )

  const handlers = {
    onPointerDown: (e: React.PointerEvent) => {
      if (e.button !== 0) return
      cancelAnimationFrame(anim.current)
      drag.current = { x: e.clientX, y: e.clientY, moved: false }
      dragged.current = false
    },
    onPointerMove: (e: React.PointerEvent) => {
      const d = drag.current
      if (!d) return
      const dx = e.clientX - d.x
      const dy = e.clientY - d.y
      if (!d.moved && Math.hypot(dx, dy) < 4) return
      if (!d.moved) ref.current?.setPointerCapture(e.pointerId)
      d.moved = true
      d.x = e.clientX
      d.y = e.clientY
      setView((v) => ({ ...v, cx: v.cx - dx * (v.w / size.w), cy: v.cy - dy * (v.w / size.w) }))
    },
    onPointerUp: () => {
      dragged.current = drag.current?.moved ?? false
      drag.current = null
    },
    // Clicks that end a drag must not select map objects.
    onClickCapture: (e: React.MouseEvent) => {
      if (dragged.current) e.stopPropagation()
      dragged.current = false
    },
  }

  return {
    ref,
    viewBox: `${view.cx - view.w / 2} ${view.cy - h / 2} ${view.w} ${h}`,
    // Visible area in meters, for layers that must cover the whole view (the grid).
    bounds: { x0: view.cx - view.w / 2, y0: view.cy - h / 2, x1: view.cx + view.w / 2, y1: view.cy + h / 2 },
    mpp,
    flyTo,
    fit,
    handlers,
  }
}
