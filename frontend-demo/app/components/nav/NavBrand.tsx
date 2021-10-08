import Image from "next/image";
import Link from "next/link";

export default function NavBrand() {
  return (
    <Link
      href="/"
      className="flex shrink-0 items-center gap-1.5 font-mono font-bold no-underline md:gap-2"
    >
      <Image
        src="/chatvector-logo-dark.svg"
        alt=""
        width={70}
        height={70}
        unoptimized
        className="size-9 shrink-0 md:size-10 lg:size-12 [[data-theme=light]_&]:hidden"
      />
      <Image
        src="/chatvector-logo-light.svg"
        alt=""
        width={70}
        height={70}
        unoptimized
        className="size-9 shrink-0 hidden md:size-10 lg:size-12 [[data-theme=light]_&]:block"
      />
      <span className="whitespace-nowrap text-[1.2rem] leading-tight md:text-[1.45rem] lg:text-[1.7rem] text-headline-gradient">
        ChatVector
      </span>
    </Link>
  );
}
