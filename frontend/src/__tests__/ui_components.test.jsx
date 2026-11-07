import { describe, it, expect } from "vitest";
import { cn } from "../lib/utils";
import { badgeVariants } from "../components/ui/badge";
import { buttonVariants } from "../components/ui/button";

describe("Frontend UI Utilities & Variants", () => {
  it("merges tailwind classes cleanly with clsx and twMerge", () => {
    const result = cn("px-2 py-1", "px-4", { "text-red-500": true, "text-blue-500": false });
    expect(result).toContain("px-4");
    expect(result).not.toContain("px-2");
    expect(result).toContain("text-red-500");
  });

  it("produces correct badge variants for research report audits", () => {
    const successClass = badgeVariants({ variant: "success" });
    expect(successClass).toContain("emerald");

    const warningClass = badgeVariants({ variant: "warning" });
    expect(warningClass).toContain("amber");

    const destructiveClass = badgeVariants({ variant: "destructive" });
    expect(destructiveClass).toContain("destructive");
  });

  it("produces correct button variants", () => {
    const defaultBtn = buttonVariants({ variant: "default" });
    expect(defaultBtn).toContain("bg-primary");

    const outlineBtn = buttonVariants({ variant: "outline" });
    expect(outlineBtn).toContain("border");
  });
});

