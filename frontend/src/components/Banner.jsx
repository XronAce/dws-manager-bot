/**
 * A dismissible message. `tone` is "error" or "ok".
 *
 * Errors from the API can be long — a validation failure names the field and
 * the rule — so the text wraps and the close button stays pinned to the top
 * right rather than drifting down beside a two-line message.
 */
export default function Banner({ tone = 'error', children, onDismiss }) {
  if (!children) return null
  return (
    <div className={`banner ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <div className="banner-body">{children}</div>
      {onDismiss && (
        <button
          type="button"
          className="banner-close"
          onClick={onDismiss}
          aria-label="Dismiss message"
          title="Dismiss"
        >
          ×
        </button>
      )}
    </div>
  )
}
