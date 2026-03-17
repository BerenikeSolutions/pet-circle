'use client';

interface AddRowProps {
  label: string;
  onClick: () => void;
}

export default function AddRow({ label, onClick }: AddRowProps) {
  return (
    <button
      onClick={onClick}
      className="w-full py-3 border-2 border-dashed border-brand/30 rounded-xl text-brand text-sm font-semibold hover:border-brand/50 hover:bg-brand/5 transition-colors"
    >
      + {label}
    </button>
  );
}
