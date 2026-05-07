import Tooltip, { tooltip } from "./Tooltip.astro";
import TooltipContent, { tooltipContent } from "./TooltipContent.astro";

const TooltipVariants = {
  tooltip,
  tooltipContent,
};

export { Tooltip, TooltipContent, TooltipVariants };

export default {
  Root: Tooltip,
  Content: TooltipContent,
};
