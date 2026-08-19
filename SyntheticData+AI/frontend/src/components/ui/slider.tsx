import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";
import { cn } from "@/lib/utils";

/**
 * `label` lands on the thumb, not the root: Radix puts `role="slider"` on the
 * thumb, so an aria-label on the root leaves the actual control unnamed to a
 * screen reader.
 */
function Slider({
  className,
  label,
  ...props
}: React.ComponentProps<typeof SliderPrimitive.Root> & { label?: string }) {
  return (
    <SliderPrimitive.Root
      data-slot="slider"
      className={cn(
        "relative flex w-full touch-none items-center select-none data-[disabled]:opacity-50",
        className
      )}
      {...props}
    >
      <SliderPrimitive.Track className="bg-secondary relative h-1.5 w-full grow overflow-hidden rounded-full">
        <SliderPrimitive.Range className="bg-primary absolute h-full" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        aria-label={label}
        className="border-primary bg-background ring-ring/40 block size-4 shrink-0 rounded-full border-2 shadow-sm transition-[color,box-shadow] hover:ring-4 focus-visible:ring-4 focus-visible:outline-none"
      />
    </SliderPrimitive.Root>
  );
}

export { Slider };
