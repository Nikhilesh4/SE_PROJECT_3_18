export interface EducationItem {
    degree: string;
    institution: string;
    year: string;
}

export interface ExperienceItem {
    role: string;
    company: string;
    duration: string;
    summary: string;
}

export interface ProfileData {
    skills: string[];
    education: EducationItem[];
    experience: ExperienceItem[];
    interests: string[];
    updated_at?: string | null;
}
