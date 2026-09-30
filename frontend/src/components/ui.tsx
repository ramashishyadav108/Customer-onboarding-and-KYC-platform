import { useEffect, useId, useRef, type ReactNode, type SelectHTMLAttributes, type InputHTMLAttributes } from 'react';
import { REASON_TEXT } from '@/config';
import type { ReasonOption } from '@/config';
import { humanize } from '@/lib/format';

export function SkipLink() {
  return (
    <a className="skip-link" href="#main">
      Skip to main content
    </a>
  );
}

export function StatusChip({ status }: { status: string }) {
  return <span className={`chip ${status}`}>{humanize(status)}</span>;
}

export function Banner({ kind, children, live = true }: { kind: 'e' | 'ok' | 'i' | 'w'; children: ReactNode; live?: boolean }) {
  return (
    <div className={`banner ${kind}`} role={kind === 'e' && live ? 'alert' : 'status'}>
      {children}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <p className="meta" role="status">
      {children}
    </p>
  );
}

export function reasonLabel(code: string | null | undefined): string {
  if (!code) return '';
  return REASON_TEXT[code] ?? humanize(code);
}

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export function FormField({ label, error, hint, id, ...rest }: FieldProps) {
  const auto = useId();
  const fid = id ?? auto;
  const describedBy = [hint ? `${fid}-hint` : '', error ? `${fid}-err` : ''].filter(Boolean).join(' ') || undefined;
  return (
    <div className="field">
      <label htmlFor={fid}>{label}</label>
      <input id={fid} aria-invalid={error ? true : undefined} aria-describedby={describedBy} {...rest} />
      {hint && (
        <p className="hint" id={`${fid}-hint`}>
          {hint}
        </p>
      )}
      {error && (
        <p className="err" id={`${fid}-err`}>
          {error}
        </p>
      )}
    </div>
  );
}

interface SelectFieldProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label: string;
  options: ReasonOption[];
  placeholder?: string;
  error?: string;
}

export function SelectField({ label, options, placeholder, error, id, ...rest }: SelectFieldProps) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <div className="field">
      <label htmlFor={fid}>{label}</label>
      <select id={fid} aria-invalid={error ? true : undefined} aria-describedby={error ? `${fid}-err` : undefined} {...rest}>
        {placeholder !== undefined && <option value="">{placeholder}</option>}
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && (
        <p className="err" id={`${fid}-err`}>
          {error}
        </p>
      )}
    </div>
  );
}

export function ReasonSelect(props: Omit<SelectFieldProps, 'placeholder' | 'label'> & { label?: string }) {
  return <SelectField label={props.label ?? 'Reason code'} placeholder="Select a reason code" {...props} />;
}

interface DialogProps {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
}

// Modal confirm dialog: focus moves in, is trapped, Escape cancels, focus returns to opener.
export function ConfirmDialog({ title, children, confirmLabel, onConfirm, onCancel, busy }: DialogProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>('button');
    first?.focus();
    return () => opener?.focus();
  }, []);
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.stopPropagation();
      onCancel();
      return;
    }
    if (e.key !== 'Tab') return;
    const focusables = ref.current?.querySelectorAll<HTMLElement>('button:not([disabled])');
    if (!focusables || focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };
  return (
    <div className="dialog-backdrop">
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={ref} onKeyDown={onKeyDown}>
        <h2 id={titleId}>{title}</h2>
        {children}
        <div className="row" style={{ marginTop: 16 }}>
          <button type="button" className="sec" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" onClick={onConfirm} disabled={busy}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
