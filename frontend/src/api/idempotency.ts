const IDEMPOTENCY_STORAGE_PREFIX = 'easy_mes:idempotency:'

const memoryKeys = new Map<string, string>()

function storageKey(scope: string) {
  return `${IDEMPOTENCY_STORAGE_PREFIX}${scope}`
}

function getStoredKey(scope: string) {
  const key = storageKey(scope)
  if (typeof window === 'undefined') {
    return memoryKeys.get(key) ?? null
  }
  try {
    return window.sessionStorage.getItem(key)
  } catch {
    return memoryKeys.get(key) ?? null
  }
}

function setStoredKey(scope: string, value: string) {
  const key = storageKey(scope)
  if (typeof window === 'undefined') {
    memoryKeys.set(key, value)
    return
  }
  try {
    window.sessionStorage.setItem(key, value)
  } catch {
    memoryKeys.set(key, value)
  }
}

function removeStoredKey(scope: string) {
  const key = storageKey(scope)
  if (typeof window === 'undefined') {
    memoryKeys.delete(key)
    return
  }
  try {
    window.sessionStorage.removeItem(key)
  } catch {
    memoryKeys.delete(key)
  }
}

export function pendingIdempotencyKey(scope: string) {
  const existing = getStoredKey(scope)
  if (existing) {
    return existing
  }
  const next = crypto.randomUUID()
  setStoredKey(scope, next)
  return next
}

export async function withIdempotencyKey<T>(scope: string, request: (idempotencyKey: string) => Promise<T>) {
  const idempotencyKey = pendingIdempotencyKey(scope)
  const response = await request(idempotencyKey)
  removeStoredKey(scope)
  return response
}
