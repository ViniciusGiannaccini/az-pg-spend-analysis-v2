/**
 * @fileoverview IndexedDB persistence layer for taxonomy sessions.
 * 
 * This module provides the database abstraction for storing taxonomy sessions
 * locally in the browser using IndexedDB via the `idb` library.
 * 
 * Sessions are persisted with all their data (summary, analytics, items,
 * and file content) to enable full recovery after page reload.
 * 
 * @module database
 */

import { openDB, DBSchema, IDBPDatabase } from 'idb'
import type { TaxonomySession } from '@/hooks/useTaxonomySession'

// ============================================
// Database Schema
// ============================================

/**
 * IndexedDB schema definition for the Spend Analysis database.
 * Currently contains a single object store for sessions.
 */
interface SpendAnalysisDB extends DBSchema {
    /** Object store for taxonomy sessions, keyed by sessionId */
    sessions: {
        /** Primary key: sessionId */
        key: string
        /** Stored value: complete TaxonomySession object */
        value: TaxonomySession
        /** Indexes for efficient querying */
        indexes: { 'by-timestamp': string }
    }
}

// ============================================
// Database Connection
// ============================================

/** Database name in IndexedDB */
const DB_NAME = 'pg-spend-analysis'

/** Current database schema version */
const DB_VERSION = 1

let dbPromise: Promise<IDBPDatabase<SpendAnalysisDB>> | null = null

const getDB = async (): Promise<IDBPDatabase<SpendAnalysisDB>> => {
    if (typeof window === 'undefined') {
        throw new Error('IndexedDB is not available on the server')
    }

    if (!dbPromise) {
        dbPromise = openDB<SpendAnalysisDB>(DB_NAME, DB_VERSION, {
            upgrade(db) {
                // Create sessions store if it doesn't exist
                if (!db.objectStoreNames.contains('sessions')) {
                    const store = db.createObjectStore('sessions', { keyPath: 'sessionId' })
                    store.createIndex('by-timestamp', 'timestamp')
                }
            },
        })
    }

    return dbPromise
}

// ============================================
// Session Operations
// ============================================

/**
 * Save a session to IndexedDB
 */
export const saveSession = async (session: TaxonomySession): Promise<void> => {
    try {
        const db = await getDB()
        await db.put('sessions', session)
    } catch (error) {
        console.error('Error saving session to IndexedDB:', error)
    }
}

/**
 * Get a session by ID
 */
export const getSession = async (sessionId: string): Promise<TaxonomySession | undefined> => {
    try {
        const db = await getDB()
        return await db.get('sessions', sessionId)
    } catch (error) {
        console.error('Error getting session from IndexedDB:', error)
        return undefined
    }
}

/**
 * Get all sessions, sorted by timestamp (newest first)
 */
export const getAllSessions = async (): Promise<TaxonomySession[]> => {
    try {
        const db = await getDB()
        const sessions = await db.getAll('sessions')
        // Sort by timestamp descending (newest first)
        return sessions.sort((a, b) =>
            new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        )
    } catch (error) {
        console.error('Error getting all sessions from IndexedDB:', error)
        return []
    }
}

/**
 * Delete a session by ID
 */
export const deleteSession = async (sessionId: string): Promise<void> => {
    try {
        const db = await getDB()
        await db.delete('sessions', sessionId)
    } catch (error) {
        console.error('Error deleting session from IndexedDB:', error)
    }
}

/**
 * Delete all sessions (useful for cleanup)
 */
export const clearAllSessions = async (): Promise<void> => {
    try {
        const db = await getDB()
        await db.clear('sessions')
    } catch (error) {
        console.error('Error clearing sessions from IndexedDB:', error)
    }
}
