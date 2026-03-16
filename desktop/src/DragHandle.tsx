/**
 * DragHandle — thin draggable strip at the top of the overlay window.
 * Uses -webkit-app-region: drag so the user can reposition the window
 * by clicking and dragging this area.
 */
export default function DragHandle() {
  return (
    <div
      style={{
        position:          'fixed',
        top:               0,
        left:              0,
        right:             0,
        height:            24,
        WebkitAppRegion:   'drag',    // Electron drag region
        cursor:            'grab',
        zIndex:            9999,
      } as React.CSSProperties}
    />
  )
}
