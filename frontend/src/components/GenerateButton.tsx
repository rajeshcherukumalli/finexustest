import type { ReactNode } from "react";

type Props = {
  loading: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
  loadingLabel: string;
};

export default function GenerateButton({
  loading,
  disabled,
  onClick,
  children,
  loadingLabel,
}: Props) {
  return (
    <button
      type="button"
      className={loading ? "btn-loading" : undefined}
      onClick={onClick}
      disabled={disabled || loading}
    >
      {loading && <span className="spinner" aria-hidden="true" />}
      {loading ? loadingLabel : children}
    </button>
  );
}
