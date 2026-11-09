import { useEffect, useId, useRef, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import './DetailDialog.css';

interface DetailDialogProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  onClose: () => void;
}

export function DetailDialog({ title, subtitle, children, onClose }: DetailDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  const titleId = useId();
  const subtitleId = useId();

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    element.showModal();
    return () => {
      element.close();
      document.body.style.overflow = overflow;
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, []);

  return createPortal(
    <dialog
      ref={dialog}
      className="detail-dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={subtitle ? subtitleId : undefined}
      onCancel={event => { event.preventDefault(); close.current(); }}
      onClick={event => {
        if (event.target !== event.currentTarget) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) close.current();
      }}
      onKeyDown={event => {
        if (event.key !== 'Tab') return;
        const candidates = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex="0"]')).filter(element => element.getClientRects().length);
        const first = candidates[0]; const last = candidates.at(-1);
        if (!first) { event.preventDefault(); return; }
        if (event.shiftKey && (document.activeElement === first || document.activeElement === event.currentTarget)) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }}
    >
      <header className="detail-dialog-header">
        <div><h2 id={titleId}>{title}</h2>{subtitle && <p id={subtitleId}>{subtitle}</p>}</div>
        <button type="button" className="detail-dialog-close" aria-label="Close details" onClick={onClose} autoFocus><X size={21} /></button>
      </header>
      <div className="detail-dialog-content">{children}</div>
    </dialog>, document.body,
  );
}
