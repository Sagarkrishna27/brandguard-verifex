const configuredBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export const API_BASE_URL = configuredBase.replace(/\/$/, '')
export const apiUrl = (path) => `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`

export async function apiRequest(url, options = {}, {
	timeoutMs = 30_000,
	fallbackMessage = 'The BrandGuard API request failed.',
} = {}) {
	const controller = new AbortController()
	const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs)

	try {
		const response = await fetch(url, { ...options, signal: controller.signal })
		let data

		try {
			data = await response.json()
		} catch {
			throw new Error('The BrandGuard API returned an invalid response.')
		}

		if (!response.ok) {
			throw new Error(typeof data.detail === 'string' ? data.detail : fallbackMessage)
		}

		return data
	} catch (error) {
		if (controller.signal.aborted) {
			throw new Error(`Request timed out after ${Math.ceil(timeoutMs / 1000)} seconds.`, { cause: error })
		}
		const message = error instanceof Error ? error.message : fallbackMessage
		throw new Error(message, { cause: error })
	} finally {
		globalThis.clearTimeout(timeoutId)
	}
}
