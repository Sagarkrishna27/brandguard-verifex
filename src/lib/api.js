const configuredBase = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export const API_BASE_URL = configuredBase.replace(/\/$/, '')
export const apiUrl = (path) => `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`

let requestSequence = 0

export async function apiRequest(url, options = {}, {
	timeoutMs = 120_000,
	fallbackMessage = 'The BrandGuard API request failed.',
} = {}) {
	const controller = new AbortController()
	const requestId = ++requestSequence
	const dispatchStatus = (status) => {
		if (typeof window !== 'undefined') {
			window.dispatchEvent(new CustomEvent('brandguard:api-request', {
				detail: { requestId, status },
			}))
		}
	}
	const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs)
	const slowId = globalThis.setTimeout(() => dispatchStatus('slow'), 10_000)
	dispatchStatus('start')

	try {
		const response = await fetch(url, { ...options, signal: controller.signal })
		const responseText = await response.text()
		let data = {}

		if (responseText) {
			try {
				data = JSON.parse(responseText)
			} catch {
				if (response.ok) {
					throw new Error('The BrandGuard API returned an invalid response.')
				}
			}
		}

		if (!response.ok) {
			const error = new Error(`HTTP ${response.status}: ${responseText || fallbackMessage}`)
			error.isHttpError = true
			throw error
		}

		return data
	} catch (error) {
		if (error.isHttpError) throw error
		if (controller.signal.aborted) {
			throw new Error('The server is waking up or is busy. Please wait a minute and try again.', { cause: error })
		}
		if (error instanceof TypeError || error.name === 'AbortError') {
			throw new Error('The server is waking up or is busy. Please wait a minute and try again.', { cause: error })
		}
		const message = error instanceof Error ? error.message : fallbackMessage
		throw new Error(message, { cause: error })
	} finally {
		globalThis.clearTimeout(timeoutId)
		globalThis.clearTimeout(slowId)
		dispatchStatus('finish')
	}
}
