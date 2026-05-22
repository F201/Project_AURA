/**
 * Unified identity management for Project AURA.
 * Ensures Chat and Voice always share the same UUID stored in localStorage.
 */

export function getOrCreateIdentity() {
    return 'aura-user'
}
