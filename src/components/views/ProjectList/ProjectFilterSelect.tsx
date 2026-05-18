import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type ProjectFilterSelectProps = {
  placeholder: string;
  options: string[];
  value: string;
  onDispatch: (value: string) => void;
};

const ProjectFilterSelect = ({
  placeholder,
  options,
  value,
  onDispatch,
}: ProjectFilterSelectProps) => {
  return (
    <Select value={value} onValueChange={onDispatch}>
      <SelectTrigger className="h-10 min-w-[110px] rounded-full border-[#E5E7EB] bg-white px-4 text-[#4B5563] shadow-none">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option} value={option}>
            {option}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};

export default ProjectFilterSelect;
