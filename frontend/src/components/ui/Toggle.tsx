'use client';

interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
}

export default function Toggle({ checked, onChange, label }: ToggleProps) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      {label && <span className="text-xs text-gray-500">{label}</span>}
      <div
        className="relative w-10 h-[22px] rounded-full transition-colors duration-200"
        style={{ backgroundColor: checked ? '#D44800' : '#E5E5EA' }}
        onClick={() => onChange(!checked)}
      >
        <div
          className="absolute top-[2px] w-[18px] h-[18px] bg-white rounded-full shadow transition-transform duration-200"
          style={{ transform: checked ? 'translateX(20px)' : 'translateX(2px)' }}
        />
      </div>
    </label>
  );
}
