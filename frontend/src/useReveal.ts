import { useEffect, useRef, useState } from 'react'

/** True once the element has scrolled into view (then stays true).
 *  Drives the "squeegee" print reveal on product photos and section fade-ins. */
export function useReveal<T extends Element>() {
  const ref = useRef<T>(null)
  // Without IntersectionObserver (very old browsers) show everything at once instead of
  // leaving photos hidden behind an animation that would never start.
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === 'undefined')

  useEffect(() => {
    const element = ref.current
    if (!element || visible) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.15 },
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [visible])

  return { ref, visible }
}
