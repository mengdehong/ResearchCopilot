/**
 * useVoiceInput — 统一语音输入 hook。
 *
 * 默认使用浏览器 Web Speech API 实时转写，
 * 不可用时自动回退到 Groq Whisper 后端 API。
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import api from '@/lib/api'

// ─── Types ───

type VoiceStatus = 'idle' | 'recording' | 'transcribing' | 'error'
type EngineType = 'web-speech' | 'groq-whisper'

interface UseVoiceInputReturn {
    status: VoiceStatus
    interimText: string
    error: string | null
    engineType: EngineType
    elapsedSeconds: number
    startRecording: () => Promise<void>
    stopRecording: () => void
    cancelRecording: () => void
}

// ─── Web Speech API type shim ───

interface SpeechRecognitionEvent {
    resultIndex: number
    results: SpeechRecognitionResultList
}

interface SpeechRecognitionErrorEvent {
    error: string
    message?: string
}

interface SpeechRecognitionInstance extends EventTarget {
    continuous: boolean
    interimResults: boolean
    lang: string
    start: () => void
    stop: () => void
    abort: () => void
    onresult: ((event: SpeechRecognitionEvent) => void) | null
    onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
    onend: (() => void) | null
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance

// ─── Helpers ───

const MAX_RECORDING_MS = 5 * 60 * 1000 // 5 minutes

function getSpeechRecognitionCtor(): SpeechRecognitionConstructor | null {
    const w = window as unknown as Record<string, unknown>
    return (w.SpeechRecognition ?? w.webkitSpeechRecognition) as SpeechRecognitionConstructor | null
}

function detectEngine(preferred?: EngineType): EngineType {
    if (preferred) return preferred
    return getSpeechRecognitionCtor() ? 'web-speech' : 'groq-whisper'
}

// ─── Hook ───

export default function useVoiceInput(
    onTranscript: (text: string) => void,
    engine?: EngineType,
): UseVoiceInputReturn {
    const [status, setStatus] = useState<VoiceStatus>('idle')
    const [interimText, setInterimText] = useState('')
    const [error, setError] = useState<string | null>(null)
    const [elapsedSeconds, setElapsedSeconds] = useState(0)

    const engineType = detectEngine(engine)

    // Refs to hold mutable state across callbacks
    const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)
    const mediaRecorderRef = useRef<MediaRecorder | null>(null)
    const mediaStreamRef = useRef<MediaStream | null>(null)
    const chunksRef = useRef<Blob[]>([])
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
    const maxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const onTranscriptRef = useRef(onTranscript)
    const manualStopRef = useRef(false)

    // Keep onTranscript ref fresh
    useEffect(() => {
        onTranscriptRef.current = onTranscript
    }, [onTranscript])

    // ─── Timer ───

    const startTimer = useCallback(() => {
        setElapsedSeconds(0)
        timerRef.current = setInterval(() => {
            setElapsedSeconds((s) => s + 1)
        }, 1000)
    }, [])

    const stopTimer = useCallback(() => {
        if (timerRef.current) {
            clearInterval(timerRef.current)
            timerRef.current = null
        }
        if (maxTimerRef.current) {
            clearTimeout(maxTimerRef.current)
            maxTimerRef.current = null
        }
    }, [])

    // ─── Cleanup ───

    const cleanup = useCallback(() => {
        stopTimer()

        if (recognitionRef.current) {
            recognitionRef.current.onresult = null
            recognitionRef.current.onerror = null
            recognitionRef.current.onend = null
            recognitionRef.current.abort()
            recognitionRef.current = null
        }

        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop()
        }
        mediaRecorderRef.current = null

        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach((t) => t.stop())
            mediaStreamRef.current = null
        }

        chunksRef.current = []
    }, [stopTimer])

    // Cleanup on unmount
    useEffect(() => cleanup, [cleanup])

    // ─── Web Speech Engine ───

    const startWebSpeech = useCallback(async () => {
        const Ctor = getSpeechRecognitionCtor()
        if (!Ctor) {
            setError('Web Speech API not available')
            setStatus('error')
            return
        }

        const recognition = new Ctor()
        recognition.continuous = true
        recognition.interimResults = true
        recognition.lang = document.documentElement.lang === 'zh' ? 'zh-CN' : 'en-US'
        recognitionRef.current = recognition
        manualStopRef.current = false

        recognition.onresult = (event: SpeechRecognitionEvent) => {
            let interim = ''
            let final = ''
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript
                if (event.results[i].isFinal) {
                    final += transcript
                } else {
                    interim += transcript
                }
            }
            if (final) {
                onTranscriptRef.current(final)
            }
            setInterimText(interim)
        }

        recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
            if (event.error === 'not-allowed') {
                setError('mic-permission-denied')
            } else {
                setError(event.error)
            }
            cleanup()
            setStatus('error')
        }

        recognition.onend = () => {
            // If manually stopped, don't auto-restart
            if (manualStopRef.current) {
                setInterimText('')
                cleanup()
                setStatus('idle')
                return
            }
            // Web Speech API can auto-stop — restart if still recording
            if (recognitionRef.current) {
                try {
                    recognitionRef.current.start()
                } catch {
                    cleanup()
                    setStatus('idle')
                }
            }
        }

        try {
            recognition.start()
            setStatus('recording')
            setError(null)
            startTimer()

            maxTimerRef.current = setTimeout(() => {
                manualStopRef.current = true
                recognition.stop()
            }, MAX_RECORDING_MS)
        } catch {
            setError('Failed to start speech recognition')
            setStatus('error')
        }
    }, [cleanup, startTimer])

    // ─── Groq Whisper Engine ───

    const startGroqWhisper = useCallback(async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
            mediaStreamRef.current = stream

            const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
            mediaRecorderRef.current = recorder
            chunksRef.current = []

            recorder.ondataavailable = (e: BlobEvent) => {
                if (e.data.size > 0) {
                    chunksRef.current.push(e.data)
                }
            }

            recorder.onstop = async () => {
                stopTimer()

                if (chunksRef.current.length === 0) {
                    setStatus('idle')
                    cleanup()
                    return
                }

                setStatus('transcribing')
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
                const formData = new FormData()
                formData.append('file', blob, 'recording.webm')
                formData.append('language', document.documentElement.lang === 'zh' ? 'zh' : 'en')

                try {
                    const response = await api.post('/stt/transcribe', formData, {
                        headers: { 'Content-Type': 'multipart/form-data' },
                    })
                    const text = response.data.text as string
                    if (text.trim()) {
                        onTranscriptRef.current(text.trim())
                    }
                    setStatus('idle')
                } catch {
                    setError('transcription-failed')
                    setStatus('error')
                } finally {
                    cleanup()
                }
            }

            recorder.start(1000) // collect data every second
            setStatus('recording')
            setError(null)
            startTimer()

            maxTimerRef.current = setTimeout(() => {
                if (mediaRecorderRef.current?.state === 'recording') {
                    mediaRecorderRef.current.stop()
                }
            }, MAX_RECORDING_MS)
        } catch (err) {
            const e = err as DOMException
            if (e.name === 'NotAllowedError') {
                setError('mic-permission-denied')
            } else {
                setError('Failed to access microphone')
            }
            setStatus('error')
            cleanup()
        }
    }, [cleanup, startTimer, stopTimer])

    // ─── Public API ───

    const startRecording = useCallback(async () => {
        if (status !== 'idle' && status !== 'error') return
        setError(null)
        setInterimText('')

        if (engineType === 'web-speech') {
            await startWebSpeech()
        } else {
            await startGroqWhisper()
        }
    }, [status, engineType, startWebSpeech, startGroqWhisper])

    const stopRecording = useCallback(() => {
        if (status !== 'recording') return

        if (engineType === 'web-speech' && recognitionRef.current) {
            manualStopRef.current = true
            recognitionRef.current.stop()
        } else if (mediaRecorderRef.current?.state === 'recording') {
            mediaRecorderRef.current.stop()
        }
    }, [status, engineType])

    const cancelRecording = useCallback(() => {
        manualStopRef.current = true
        chunksRef.current = [] // discard recorded data
        cleanup()
        setStatus('idle')
        setInterimText('')
        setError(null)
    }, [cleanup])

    return {
        status,
        interimText,
        error,
        engineType,
        elapsedSeconds,
        startRecording,
        stopRecording,
        cancelRecording,
    }
}
