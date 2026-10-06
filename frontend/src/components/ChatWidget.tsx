import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  fetchChatHistory,
  formatPrice,
  pageContextFor,
  sendChat,
  type BrowseLink,
  type ChatTurn,
  type PageType,
  type ProductCardData,
} from '../api'
import { useAuth } from '../auth-context'
import YH_Bulldog from './YH_Bulldog'

interface ChatMessage extends ChatTurn {
  products?: ProductCardData[]
  browse?: BrowseLink | null
  error?: boolean
}

// Guests only: how many earlier messages go to the agent with each question (keeps
// follow-ups like "is it in medium?" working). A logged-in customer's history is loaded
// by the server from the database instead.
const HISTORY_SENT = 12

// Starter questions that fit the page the shopper is on.
const SUGGESTIONS: Partial<Record<PageType, string[]>> & { default: string[] } = {
  product: ['Is my size in stock?', 'Does this come in other colors?', 'Show me similar styles'],
  products: ['Help me find a gift under $60', 'What hoodies do you have?', 'Anything with Handsome Dan?'],
  default: ['What hoodies do you have?', 'Gifts for my dad', 'Anything with Handsome Dan?'],
}

const DAN_COAT = '#f8f6f1'

export default function ChatWidget() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [waiting, setWaiting] = useState(false)
  const [savedCount, setSavedCount] = useState(0) // messages reloaded from the account
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()
  const page = pageContextFor(pathname)

  // A logged-in customer's earlier conversation is reloaded from the database.
  // (This component is re-created on log-in/log-out, so it runs once per person.)
  useEffect(() => {
    if (!user) return
    let cancelled = false // ignore a stale response (React runs effects twice in development)
    fetchChatHistory().then((saved) => {
      if (cancelled) return
      setMessages((current) => [...saved, ...current])
      setSavedCount(saved.length)
    })
    return () => {
      cancelled = true
    }
  }, [user])

  const greeting = user
    ? savedCount > 0
      ? `Welcome back, ${user.first_name}! Dan here. Your earlier chat is above. What can I sniff out for you today?`
      : `Hi ${user.first_name}, I'm Dan, the shop bulldog. Ask me about any piece: price, sizes, what's actually on the shelf.`
    : "Hi, I'm Dan, the Campus Customs shop bulldog. Ask me about any piece: price, sizes, what's actually on the shelf."

  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  // Keep the newest message in view. Card images load after the text, so scroll again when
  // one finishes loading (see onLoad below).
  // Block body on purpose: scrollTo() returns a Promise in recent Chrome, and an effect that
  // returns a non-function crashes React (same bug as App.tsx's ScrollToTop in Problem 3).
  const scrollToBottom = () => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }
  useEffect(() => {
    scrollToBottom()
  }, [messages, waiting, open])

  const ask = async (text: string) => {
    const question = text.trim()
    if (!question || waiting) return
    const history: ChatTurn[] = messages
      .filter((m) => !m.error)
      .slice(-HISTORY_SENT)
      .map(({ role, content }) => ({ role, content }))
    setMessages((current) => [...current, { role: 'user', content: question }])
    setDraft('')
    setWaiting(true)
    try {
      const reply = await sendChat(question, user ? [] : history, pageContextFor(pathname))
      setMessages((current) => [
        ...current,
        { role: 'assistant', content: reply.message, products: reply.products, browse: reply.browse },
      ])
    } catch (err) {
      const content = err instanceof Error ? err.message : 'Something went wrong. Please try again.'
      setMessages((current) => [...current, { role: 'assistant', content, error: true }])
    } finally {
      setWaiting(false)
      inputRef.current?.focus()
    }
  }

  // "Ask Dan" buttons elsewhere on the site (e.g. the product page) open the chat and send
  // their question. The ref always points at the latest ask(), with the current page.
  const askRef = useRef(ask)
  useEffect(() => {
    askRef.current = ask
  })
  useEffect(() => {
    const onAsk = (event: Event) => {
      setOpen(true)
      void askRef.current((event as CustomEvent<string>).detail)
    }
    window.addEventListener('ask-dan', onAsk)
    return () => window.removeEventListener('ask-dan', onAsk)
  }, [])

  // On a phone the open panel covers the page, so close it to reveal the product page.
  // On wider screens it stays open beside the page for follow-up questions.
  const onCardClick = () => {
    if (window.matchMedia('(max-width: 760px)').matches) setOpen(false)
  }

  const renderMessage = (message: ChatMessage, key: string) => (
    <div key={key} className={`chat-turn ${message.role}`}>
      <div className={`chat-bubble ${message.role} ${message.error ? 'error' : ''}`}>{message.content}</div>
      {message.products && message.products.length > 0 && (
        <div className="chat-cards">
          {message.products.map((product) => (
            <Link key={product.product_id} to={product.url} className="chat-card" onClick={onCardClick}>
              <img src={product.image_url} alt="" onLoad={scrollToBottom} />
              <span className="chat-card-body">
                <span className="chat-card-name">{product.name}</span>
                <span className="chat-card-desc">{product.short_description}</span>
                <span className="chat-card-meta">
                  <strong>{formatPrice(product.price)}</strong>
                  {product.total_stock > 0 ? ` · In stock: ${product.sizes_in_stock.join(', ')}` : ' · Sold out'}
                </span>
              </span>
            </Link>
          ))}
        </div>
      )}
      {message.browse && (
        <Link to={message.browse.url} className="chat-browse" onClick={onCardClick}>
          <span className="chat-browse-label">{message.browse.label}</span>
          <span aria-hidden="true">→</span>
        </Link>
      )}
    </div>
  )

  const submit = (event: FormEvent) => {
    event.preventDefault()
    void ask(draft)
  }

  const suggestions = SUGGESTIONS[page.page_type] ?? SUGGESTIONS.default

  return (
    <div className="chat-widget">
      {open && (
        <section className="chat-panel" role="dialog" aria-label="Ask Dan, the Campus Customs chat">
          <header className="chat-header">
            <YH_Bulldog furColor={DAN_COAT} bandanaColor="#286dc0" size={42} className="chat-avatar" />
            <div className="chat-header-text">
              <p className="chat-title">Ask Dan</p>
              <p className="chat-subtitle">
                <span className="online-dot" aria-hidden="true" /> Shop bulldog · real prices &amp; stock
              </p>
            </div>
            <button className="chat-close" aria-label="Close chat" onClick={() => setOpen(false)}>
              ×
            </button>
          </header>

          <div className="chat-messages" ref={listRef} aria-live="polite">
            {savedCount > 0 && <p className="chat-divider">Saved to your account</p>}
            {messages.slice(0, savedCount).map((message, index) => renderMessage(message, `saved-${index}`))}
            {savedCount > 0 && <p className="chat-divider">Today</p>}
            <div className="chat-bubble assistant">{greeting}</div>
            {!user && (
              <p className="chat-guest-note">
                Chatting as a guest, so this conversation isn't saved. <Link to="/login">Log in</Link> to keep it.
              </p>
            )}
            {messages.length === savedCount && (
              <div className="chat-suggestions">
                {suggestions.map((suggestion) => (
                  <button key={suggestion} onClick={() => void ask(suggestion)}>
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
            {messages.slice(savedCount).map((message, index) => renderMessage(message, `new-${index}`))}
            {waiting && (
              <div className="chat-typing" aria-label="Dan is checking the shelves">
                <YH_Bulldog furColor={DAN_COAT} bandanaColor="#286dc0" size={30} className="dan-thinking" />
                <span className="chat-typing-text">Dan is checking the shelves</span>
                <span className="chat-typing-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
              </div>
            )}
          </div>

          <form className="chat-input" onSubmit={submit}>
            <input
              ref={inputRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask Dan about a hoodie, a size, a price…"
              aria-label="Message"
              maxLength={1000}
            />
            <button type="submit" disabled={!draft.trim() || waiting}>
              Send
            </button>
          </form>
        </section>
      )}
      <button
        className={`chat-launcher ${open ? 'is-open' : ''}`}
        aria-label={open ? 'Close chat' : 'Ask Dan, the shop assistant'}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? (
          <svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
          </svg>
        ) : (
          <>
            <YH_Bulldog furColor={DAN_COAT} bandanaColor="#286dc0" size={44} className="launcher-dan" />
            <span className="launcher-label">Ask Dan</span>
          </>
        )}
      </button>
    </div>
  )
}
