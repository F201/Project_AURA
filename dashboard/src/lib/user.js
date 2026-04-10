/**
 * Unified identity management for Project AURA.
 * Ensures Chat and Voice always share the same UUID stored in localStorage.
 */

export function getOrCreateIdentity() {
    const KEY = 'aura_user_identity'
    let id = localStorage.getItem(KEY)

    if (!id) {
        // Generate a clean 8-char random ID for display/tracking
        // and a full UUID if needed, but here we just need a unique string.
        id = `user-${Math.random().toString(36).substring(2, 10)}`
        localStorage.setItem(KEY, id)
    }

    return id
}
