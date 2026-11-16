import { forwardRef, type SVGProps } from "react";
import Adspirer from "./Adspirer";

type AdspirerIconProps = SVGProps<SVGSVGElement> & {
  isDark?: boolean;
};

// The mark sits on its own white tile, so one drawing reads on both light and dark
// backgrounds and isDark is accepted but not needed.
export const AdspirerIcon = forwardRef<SVGSVGElement, AdspirerIconProps>(
  ({ isDark: _isDark, ...props }, ref) => <Adspirer ref={ref} {...props} />,
);
