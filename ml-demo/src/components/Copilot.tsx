import { useState, useRef, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Bot, X, Send, Sparkles, ArrowUpRight } from 'lucide-react';
import { askCopilot } from '@/api';

interface Msg { role: 'user' | 'ai'; text: string }

// The copilot answers these from the live ML models. Kept always visible so
// the user can always pick a question the assistant can respond to.
const PROMPTS = [
  'Any anomalies this week?',
  'Which assets are wasting money?',
  "What's in demand next week?",
  'Which machines need maintenance?',
  'Demand by country',
  "Summarize today's fleet",
  "How's MAC00006?",
];

export function Copilot() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([
    { role: 'ai', text: "Hi — I'm your fleet copilot. I answer live from the ML models. Ask me, or pick a prompt below." },
  ]);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, typing]);

  const send = async (text: string) => {
    if (!text.trim() || typing) return;
    setMessages((m) => [...m, { role: 'user', text }]);
    setInput('');
    setTyping(true);
    try {
      const reply = await askCopilot(text);
      setMessages((m) => [...m, { role: 'ai', text: reply }]);
    } catch {
      setMessages((m) => [...m, { role: 'ai', text: "I couldn't reach the ML backend. Make sure it's running on :8000." }]);
    } finally {
      setTyping(false);
    }
  };

  return (
    <>
      <motion.button
        whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-2xl bg-cat text-ink-900 shadow-glow"
        aria-label="CAT Copilot"
      >
        <AnimatePresence mode="wait">
          {open ? (
            <motion.span key="x" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }}><X className="h-6 w-6" /></motion.span>
          ) : (
            <motion.span key="b" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }}><Bot className="h-6 w-6" /></motion.span>
          )}
        </AnimatePresence>
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.96 }} transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="fixed bottom-24 right-6 z-50 flex h-[34rem] w-[23rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-ink-700/95 shadow-card backdrop-blur-xl"
          >
            <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-3.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-cat/15 text-cat"><Sparkles className="h-5 w-5" /></div>
              <div>
                <div className="text-sm font-semibold text-white">CAT Copilot</div>
                <div className="flex items-center gap-1.5 text-[10px] text-ink-200">
                  <span className="h-1.5 w-1.5 rounded-full bg-ok animate-pulse-soft" /> Live · Fleet-aware
                </div>
              </div>
              <button onClick={() => setOpen(false)} className="ml-auto text-ink-200 hover:text-white"><X className="h-4 w-4" /></button>
            </div>

            <div ref={scrollRef} className="scrollbar-thin flex-1 space-y-3 overflow-y-auto p-4">
              {messages.map((m, i) => (
                <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                  className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[86%] whitespace-pre-line rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
                    m.role === 'user' ? 'rounded-br-md bg-cat text-ink-900' : 'rounded-bl-md bg-ink-500/60 text-ink-50'}`}>
                    {m.text}
                  </div>
                </motion.div>
              ))}
              {typing && (
                <div className="flex justify-start">
                  <div className="flex gap-1 rounded-2xl rounded-bl-md bg-ink-500/60 px-4 py-3">
                    {[0, 1, 2].map((i) => (
                      <motion.span key={i} className="h-1.5 w-1.5 rounded-full bg-ink-100"
                        animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }} />
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Always-visible prompts */}
            <div className="border-t border-white/[0.06] px-3 pt-2.5">
              <div className="mb-1.5 flex items-center gap-1 text-[10px] font-medium uppercase tracking-wider text-ink-200">
                <Sparkles className="h-3 w-3 text-cat" /> Try asking
              </div>
              <div className="scrollbar-thin flex gap-1.5 overflow-x-auto pb-1">
                {PROMPTS.map((p) => (
                  <button key={p} onClick={() => send(p)} disabled={typing}
                    className="group flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border border-white/10 bg-ink-600/50 px-3 py-1.5 text-[11px] text-ink-100 transition-colors hover:border-cat/30 hover:bg-ink-500/50 disabled:opacity-40">
                    {p}<ArrowUpRight className="h-3 w-3 text-ink-200 transition-colors group-hover:text-cat" />
                  </button>
                ))}
              </div>
            </div>

            <div className="border-t border-white/[0.06] p-3">
              <form onSubmit={(e) => { e.preventDefault(); send(input); }} className="flex items-center gap-2">
                <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about your fleet…"
                  className="flex-1 rounded-lg border border-white/[0.06] bg-ink-600/60 px-3 py-2 text-sm text-ink-50 placeholder:text-ink-200 focus:border-cat/40 focus:outline-none" />
                <button type="submit" className="flex h-9 w-9 items-center justify-center rounded-lg bg-cat text-ink-900 transition-colors hover:bg-cat-soft"><Send className="h-4 w-4" /></button>
              </form>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
