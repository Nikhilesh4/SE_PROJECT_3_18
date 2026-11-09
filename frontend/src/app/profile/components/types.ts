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

export interface SocialLink {
    label: string;
    url: string;
}

export interface ProfileData {
    name?: string;
    socials?: SocialLink[];
    skills: string[];
    education: EducationItem[];
    experience: ExperienceItem[];
    interests: string[];
    updated_at?: string | null;
    from_cache: boolean;
}
