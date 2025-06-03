'use client';

import { useEffect } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import confetti from 'canvas-confetti';

export default function LlamaPartyPage() {
  // Trigger confetti on page load
  useEffect(() => {
    const timer = setTimeout(() => {
      celebrate();
    }, 500);

    return () => clearTimeout(timer);
  }, []);

  const celebrate = () => {
    // Fire confetti from both sides
    confetti({
      particleCount: 500,
      spread: 90,
      origin: { y: 0.6, x: 0.1 }
    });
    confetti({
      particleCount: 500,
      spread: 90,
      origin: { y: 0.6, x: 0.9 }
    });
  };

  return (
    <div className="flex flex-col min-h-screen p-8 items-center justify-center font-[family-name:var(--font-geist-sans)]">
      <Image
        src={`${process.env.NEXT_PUBLIC_BASE_PATH}/logo-dark-light.svg`}
        alt="LlamaIndex logo"
        width={120}
        height={120}
        className="mb-8"
      />

      <div className="max-w-lg p-6 bg-white dark:bg-gray-800 rounded-lg shadow-md text-center">
        <h2 className="text-xl font-bold mb-4">Congratulations!</h2>
        <p className="text-gray-600 mb-6">You found the secret page!</p>

        <div className="flex flex-col gap-4">
          <button
            onClick={celebrate}
            className="py-2 px-4 bg-foreground text-background rounded-md hover:opacity-80"
          >
            Celebrate again
          </button>

          <Link
            href="/"
            className="py-2 px-4 bg-white text-foreground border border-gray-300 rounded-md hover:bg-gray-50 text-center"
          >
            Back to workflow
          </Link>
        </div>
      </div>
    </div>
  );
}
