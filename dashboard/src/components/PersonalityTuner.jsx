const SLIDERS = [
    { key: 'empathy', label: 'Empathy' },
    { key: 'humor', label: 'Humor' },
    { key: 'formality', label: 'Formality' },
]

export default function PersonalityTuner({ settings, onUpdate }) {
    if (!settings) return <TunerSkeleton />

    return (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm">
            <h3 className="text-xl font-bold mb-8 flex items-center gap-2">
                <span className="material-icons-round text-primary">tune</span>
                Personality Tuner
            </h3>

            <div className="space-y-8">
                {SLIDERS.map(({ key, label }) => (
                    <div key={key} className="space-y-3">
                        <div className="flex justify-between text-sm font-medium">
                            <label className="text-slate-500">{label}</label>
                            <span className="text-primary">{settings[key]}%</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={settings[key]}
                            onChange={(e) => onUpdate({ [key]: parseInt(e.target.value) })}
                            className="w-full h-2 bg-slate-100 rounded-lg appearance-none cursor-pointer slider-thumb accent-primary"
                        />
                    </div>
                ))}
            </div>

            <div className="mt-10">
                <label className="block text-sm font-bold text-slate-500 uppercase tracking-widest mb-3">
                    System Prompt Override
                </label>
                <textarea
                    value={settings.system_prompt}
                    onChange={(e) => onUpdate({ system_prompt: e.target.value })}
                    placeholder="Enter core instructions here..."
                    className="w-full h-32 bg-bg-light border border-slate-200 rounded-lg p-4 font-mono text-sm focus:ring-primary focus:border-primary custom-scrollbar resize-none outline-none"
                />
            </div>
        </div>
    )
}

function TunerSkeleton() {
    return (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-sm animate-pulse">
            <div className="h-7 w-48 bg-slate-200 rounded mb-8" />
            <div className="space-y-8">
                {[1, 2, 3].map((i) => (
                    <div key={i} className="space-y-3">
                        <div className="h-4 w-24 bg-slate-200 rounded" />
                        <div className="h-2 w-full bg-slate-100 rounded-full" />
                    </div>
                ))}
            </div>
            <div className="mt-10">
                <div className="h-4 w-36 bg-slate-200 rounded mb-3" />
                <div className="h-32 w-full bg-slate-100 rounded-lg" />
            </div>
        </div>
    )
}
