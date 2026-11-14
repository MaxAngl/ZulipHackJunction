import { useEffect, useRef, useState } from 'react'
import { ApiError, join, type Role } from '../api/client'
import {
  readClinicianEmail,
  readUserProfile,
  saveClinicianEmail,
  saveToken,
  saveUserProfile,
} from '../session'

const STARTERS: Record<Role, string[]> = {
  patient: ['gardening', 'jazz', 'baking', 'reading', 'chess', 'knitting'],
  helper: [
    'cooking',
    'cycling',
    'photography',
    'hiking',
    'woodworking',
    'board games',
  ],
}

const COPY: Record<Role, { title: string; ask: string }> = {
  patient: {
    title: 'Welcome.',
    ask: 'What do you like, or know a thing or two about?',
  },
  helper: {
    title: 'Join the community.',
    ask: 'What are you into these days?',
  },
}

const MOOMIN_AVATARS = [
  { id: 'muumipeikko', name: 'Moomintroll', src: '/moomins/Muumipeikko2.jpg' },
  { id: 'muumipappa', name: 'Moominpappa', src: '/moomins/Muumipappa2.jpg' },
  { id: 'snufkin', name: 'Snufkin', src: '/moomins/Nuuskamuikkunen.png' },
  { id: 'family', name: 'Moomin Family', src: '/moomins/Characters-04-2.svg' },
]

type JoinFormProps = {
  role: Role
  onJoined: (token: string) => void
}

function JoinForm({ role, onJoined }: JoinFormProps) {
  const existingProfile = readUserProfile(role)

  const [firstName, setFirstName] = useState(
    () => existingProfile?.firstName ?? '',
  )
  const [lastName, setLastName] = useState(
    () => existingProfile?.lastName ?? '',
  )
  const [birthDate, setBirthDate] = useState(
    () => existingProfile?.birthDate ?? '',
  )
  const [city, setCity] = useState(() => existingProfile?.city ?? '')

  const initialIsMoomin =
    existingProfile?.avatarUrl?.startsWith('/moomins/') ?? false
  const [selectedMoomin, setSelectedMoomin] = useState<string | null>(() =>
    initialIsMoomin ? (existingProfile?.avatarUrl ?? null) : null,
  )
  const [rawPhoto, setRawPhoto] = useState<string | null>(() =>
    !initialIsMoomin && existingProfile?.avatarUrl
      ? existingProfile.avatarUrl
      : null,
  )
  const [avatarUrl, setAvatarUrl] = useState<string | null>(
    () => existingProfile?.avatarUrl ?? null,
  )

  // États de recadrage interactif (pan & zoom)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [imgDims, setImgDims] = useState<{ w: number; h: number }>({
    w: 130,
    h: 130,
  })
  const imgRef = useRef<HTMLImageElement>(null)
  const dragStartRef = useRef<{
    mouseX: number
    mouseY: number
    startPanX: number
    startPanY: number
  }>({
    mouseX: 0,
    mouseY: 0,
    startPanX: 0,
    startPanY: 0,
  })

  // Gestion du glisser-déposer de la souris à l'échelle de la fenêtre
  useEffect(() => {
    if (!isDragging) return

    function onMouseMove(e: MouseEvent) {
      const dx = e.clientX - dragStartRef.current.mouseX
      const dy = e.clientY - dragStartRef.current.mouseY
      setPan({
        x: dragStartRef.current.startPanX + dx,
        y: dragStartRef.current.startPanY + dy,
      })
    }

    function onMouseUp() {
      setIsDragging(false)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }
  }, [isDragging])

  const [clinicianEmail, setClinicianEmail] = useState(
    () => existingProfile?.clinicianEmail ?? readClinicianEmail() ?? '',
  )
  const [bio, setBio] = useState(() => existingProfile?.bio ?? '')
  const [passionPhotos, setPassionPhotos] = useState<string[]>(
    () => existingProfile?.passionPhotos ?? [],
  )
  const [allowProfileView, setAllowProfileView] = useState<boolean>(
    () => existingProfile?.allowProfileView ?? true,
  )
  const [interests, setInterests] = useState<string[]>(
    () => existingProfile?.interests ?? [],
  )
  const [custom, setCustom] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  function handlePassionPhotoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files
    if (!files || files.length === 0) return
    const remainingSlots = 3 - passionPhotos.length
    if (remainingSlots <= 0) return

    const toProcess = Math.min(files.length, remainingSlots)
    for (let i = 0; i < toProcess; i++) {
      const file = files[i]
      if (!file.type.startsWith('image/')) continue
      const reader = new FileReader()
      reader.onload = () => {
        if (typeof reader.result === 'string') {
          setPassionPhotos((prev) => {
            if (prev.length >= 3) return prev
            return [...prev, reader.result as string]
          })
        }
      }
      reader.readAsDataURL(file)
    }
    e.target.value = ''
  }

  function handleRemovePassionPhoto(idx: number) {
    setPassionPhotos((prev) => prev.filter((_, i) => i !== idx))
  }

  function handleAvatarFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/')) {
      setError('Please choose a valid image file.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === 'string') {
        setRawPhoto(reader.result)
        setAvatarUrl(reader.result)
        setSelectedMoomin(null)
        setZoom(1)
        setPan({ x: 0, y: 0 })
      }
    }
    reader.readAsDataURL(file)
  }

  function handleImageLoad(e: React.SyntheticEvent<HTMLImageElement>) {
    const img = e.currentTarget
    const nw = img.naturalWidth || 130
    const nh = img.naturalHeight || 130
    const V = 130
    if (nw >= nh) {
      setImgDims({ w: V * (nw / nh), h: V })
    } else {
      setImgDims({ w: V, h: V * (nh / nw) })
    }
  }

  function handleMouseDown(e: React.MouseEvent) {
    e.preventDefault()
    setIsDragging(true)
    dragStartRef.current = {
      mouseX: e.clientX,
      mouseY: e.clientY,
      startPanX: pan.x,
      startPanY: pan.y,
    }
  }

  function handleTouchStart(e: React.TouchEvent) {
    if (e.touches.length !== 1) return
    const touch = e.touches[0]
    setIsDragging(true)
    dragStartRef.current = {
      mouseX: touch.clientX,
      mouseY: touch.clientY,
      startPanX: pan.x,
      startPanY: pan.y,
    }
  }

  function handleTouchMove(e: React.TouchEvent) {
    if (!isDragging || e.touches.length !== 1) return
    const touch = e.touches[0]
    const dx = touch.clientX - dragStartRef.current.mouseX
    const dy = touch.clientY - dragStartRef.current.mouseY
    setPan({
      x: dragStartRef.current.startPanX + dx,
      y: dragStartRef.current.startPanY + dy,
    })
  }

  function handleTouchEnd() {
    setIsDragging(false)
  }

  function handleSelectMoomin(src: string) {
    if (selectedMoomin === src) {
      setSelectedMoomin(null)
      setAvatarUrl(null)
    } else {
      setSelectedMoomin(src)
      setRawPhoto(null)
      setAvatarUrl(src)
    }
  }

  function getCroppedDataUrl(): string | null {
    if (!rawPhoto) return null
    const img = imgRef.current
    if (!img || !img.complete || img.naturalWidth === 0) return rawPhoto

    const V = 130
    const C = 260
    const canvas = document.createElement('canvas')
    canvas.width = C
    canvas.height = C
    const ctx = canvas.getContext('2d')
    if (!ctx) return rawPhoto

    const nw = img.naturalWidth
    const nh = img.naturalHeight

    let W0 = V
    let H0 = V
    if (nw >= nh) {
      H0 = V
      W0 = V * (nw / nh)
    } else {
      W0 = V
      H0 = V * (nh / nw)
    }

    const W = W0 * zoom
    const H = H0 * zoom

    const X = V / 2 + pan.x - W / 2
    const Y = V / 2 + pan.y - H / 2

    const m = C / V
    ctx.drawImage(img, X * m, Y * m, W * m, H * m)
    return canvas.toDataURL('image/jpeg', 0.92)
  }

  function toggle(interest: string) {
    setInterests((current) =>
      current.includes(interest)
        ? current.filter((item) => item !== interest)
        : [...current, interest],
    )
  }

  function addCustom() {
    const value = custom.trim().toLowerCase()
    if (value && !interests.includes(value)) {
      setInterests((current) => [...current, value])
    }
    setCustom('')
  }

  async function submit() {
    setBusy(true)
    setError(null)
    try {
      const fullName = `${firstName.trim()} ${lastName.trim()}`.trim()
      const session = await join(role, fullName, interests)
      saveToken(role, session.token)

      const finalAvatar = rawPhoto
        ? (getCroppedDataUrl() ?? rawPhoto)
        : (selectedMoomin ?? avatarUrl ?? undefined)

      saveUserProfile(role, {
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        birthDate: birthDate.trim(),
        city: city.trim(),
        avatarUrl: finalAvatar,
        clinicianEmail: role === 'patient' ? clinicianEmail.trim() : undefined,
        bio: bio.trim(),
        interests,
        passionPhotos,
        allowProfileView,
      })
      if (role === 'patient' && clinicianEmail.trim() !== '') {
        saveClinicianEmail(clinicianEmail.trim())
      }
      onJoined(session.token)
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : 'The server is not responding.',
      )
    } finally {
      setBusy(false)
    }
  }

  const options = [
    ...STARTERS[role],
    ...interests.filter((item) => !STARTERS[role].includes(item)),
  ]

  const isNameReady = firstName.trim() !== '' && lastName.trim() !== ''
  const isBirthDateReady = birthDate.trim() !== ''
  const isCityReady = city.trim() !== ''
  const isAvatarReady =
    role === 'helper' ? rawPhoto !== null || avatarUrl !== null : true
  const isClinicianReady =
    role === 'patient' ? clinicianEmail.trim() !== '' : true
  const isInterestsReady = interests.length > 0

  const ready =
    isNameReady &&
    isBirthDateReady &&
    isCityReady &&
    isAvatarReady &&
    isClinicianReady &&
    isInterestsReady

  return (
    <form
      className="stack"
      onSubmit={(event) => {
        event.preventDefault()
        if (ready && !busy) void submit()
      }}
    >
      <h1>{COPY[role].title}</h1>
      <p className="quiet">
        {role === 'patient'
          ? 'Tell us a bit about you to connect at your own pace.'
          : 'Complete your helper profile to build trust and start lending a hand.'}
      </p>

      {/* Identité : prénom et nom */}
      <div className="grid-2">
        <label className="field">
          <span>
            First name <span className="required-asterisk">*</span>
          </span>
          <input
            type="text"
            value={firstName}
            maxLength={40}
            required
            autoComplete="given-name"
            placeholder="e.g. Aino"
            onChange={(event) => setFirstName(event.target.value)}
          />
        </label>
        <label className="field">
          <span>
            Last name <span className="required-asterisk">*</span>
          </span>
          <input
            type="text"
            value={lastName}
            maxLength={40}
            required
            autoComplete="family-name"
            placeholder="e.g. Virtanen"
            onChange={(event) => setLastName(event.target.value)}
          />
        </label>
      </div>

      {/* Date de naissance et Lieu de résidence */}
      <div className="grid-2">
        <label className="field">
          <span>
            Date of birth <span className="required-asterisk">*</span>
          </span>
          <input
            type="date"
            value={birthDate}
            required
            autoComplete="bday"
            onChange={(event) => setBirthDate(event.target.value)}
          />
        </label>
        <label className="field">
          <span>
            City of residence <span className="required-asterisk">*</span>
          </span>
          <input
            type="text"
            value={city}
            maxLength={60}
            required
            autoComplete="address-level2"
            placeholder="e.g. Helsinki"
            onChange={(event) => setCity(event.target.value)}
          />
        </label>
      </div>

      {/* Photo de profil avec zoom & déplacement interactif */}
      <div className="field avatar-section">
        <div className="avatar-header">
          <span>
            Profile avatar{' '}
            {role === 'helper' ? (
              <span className="required-asterisk">*</span>
            ) : (
              <span className="quiet font-small">(optional)</span>
            )}
          </span>
        </div>

        {rawPhoto ? (
          <div className="avatar-cropper-wrap">
            <div
              className="crop-viewport"
              onMouseDown={handleMouseDown}
              onTouchStart={handleTouchStart}
              onTouchMove={handleTouchMove}
              onTouchEnd={handleTouchEnd}
              title="Drag to center your photo"
            >
              <img
                ref={imgRef}
                src={rawPhoto}
                alt="Avatar"
                className="crop-img"
                draggable={false}
                onLoad={handleImageLoad}
                style={{
                  width: `${imgDims.w}px`,
                  height: `${imgDims.h}px`,
                  transform: `translate(calc(-50% + ${pan.x}px), calc(-50% + ${pan.y}px)) scale(${zoom})`,
                }}
              />
            </div>

            <p className="crop-hint">Drag photo to center</p>

            <div className="crop-controls">
              <span className="crop-zoom-label">Zoom</span>
              <input
                type="range"
                min={1}
                max={3}
                step={0.05}
                value={zoom}
                className="crop-slider"
                aria-label="Zoom photo"
                onChange={(e) => setZoom(parseFloat(e.target.value))}
              />
              <span className="crop-zoom-val">{Math.round(zoom * 100)}%</span>
            </div>

            <div className="crop-btn-row">
              <label className="button button-file button-small">
                <span>Change photo</span>
                <input
                  type="file"
                  accept="image/*"
                  className="visually-hidden"
                  onChange={handleAvatarFile}
                />
              </label>
              <button
                type="button"
                className="link quiet"
                onClick={() => {
                  setPan({ x: 0, y: 0 })
                  setZoom(1)
                }}
              >
                Reset position
              </button>
              {role === 'patient' && (
                <button
                  type="button"
                  className="link quiet"
                  onClick={() => {
                    setRawPhoto(null)
                    setAvatarUrl(null)
                  }}
                >
                  Remove
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="avatar-uploader-box">
            <div className="avatar-preview-container">
              {selectedMoomin ? (
                <img
                  src={selectedMoomin}
                  alt="Selected Moomin"
                  className="avatar-preview-img"
                />
              ) : (
                <div className="avatar-preview-placeholder">
                  <span>No photo</span>
                </div>
              )}
            </div>
            <div className="avatar-upload-actions">
              <label className="button button-file">
                <span>Upload portrait photo</span>
                <input
                  type="file"
                  accept="image/*"
                  className="visually-hidden"
                  onChange={handleAvatarFile}
                />
              </label>
              {selectedMoomin && (
                <button
                  type="button"
                  className="link quiet"
                  onClick={() => {
                    setSelectedMoomin(null)
                    setAvatarUrl(null)
                  }}
                >
                  Clear avatar
                </button>
              )}
            </div>
          </div>
        )}

        {/* Sélection Moomin pour les patients sans photo */}
        {role === 'patient' && (
          <div className="moomin-picker-section">
            <span className="moomin-picker-label">
              Or pick a Moomin character avatar:
            </span>
            <div className="moomin-grid">
              {MOOMIN_AVATARS.map((m) => {
                const isSelected = selectedMoomin === m.src
                return (
                  <button
                    key={m.id}
                    type="button"
                    className={`moomin-card ${
                      isSelected ? 'moomin-card-selected' : ''
                    }`}
                    aria-pressed={isSelected}
                    onClick={() => handleSelectMoomin(m.src)}
                  >
                    <img src={m.src} alt={m.name} className="moomin-card-img" />
                    <span className="moomin-card-name">{m.name}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {role === 'patient' && (
        <label className="field">
          <span>
            Your clinician's email <span className="required-asterisk">*</span>
          </span>
          <input
            type="email"
            value={clinicianEmail}
            required
            placeholder="doctor@clinic.org"
            autoComplete="email"
            onChange={(event) => setClinicianEmail(event.target.value)}
          />
          <small className="quiet">
            Allows your clinician to discreetly follow your remission stability
            without clinical surveys.
          </small>
        </label>
      )}

      <div className="field">
        <span>
          {COPY[role].ask} <span className="required-asterisk">*</span>
        </span>
        <div className="chips">
          {options.map((interest) => (
            <button
              key={interest}
              type="button"
              className={
                interests.includes(interest) ? 'chip chip-on' : 'chip chip-off'
              }
              aria-pressed={interests.includes(interest)}
              onClick={() => toggle(interest)}
            >
              {interest}
            </button>
          ))}
        </div>
        <div className="row">
          <input
            type="text"
            value={custom}
            maxLength={40}
            placeholder="Add your own"
            aria-label="Add your own interest"
            onChange={(event) => setCustom(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                addCustom()
              }
            }}
          />
          <button
            type="button"
            className="button"
            disabled={custom.trim() === ''}
            onClick={addCustom}
          >
            Add
          </button>
        </div>
      </div>

      {/* Bio / Quelques lignes sur vos passions */}
      <label className="field">
        <span>
          A few words about you & your passions{' '}
          <span className="quiet font-small">(optional)</span>
        </span>
        <textarea
          rows={3}
          value={bio}
          maxLength={300}
          placeholder="e.g. Sourdough bread enthusiast, nature walker, jazz records collector..."
          aria-label="Bio or passions"
          onChange={(e) => setBio(e.target.value)}
        />
      </label>

      {/* Jusqu'à 3 photos de passion */}
      <div className="field">
        <div className="flex-between">
          <span>
            Photos of your passions / hobbies{' '}
            <span className="quiet font-small">(up to 3)</span>
          </span>
          <span className="quiet font-small">{passionPhotos.length}/3</span>
        </div>
        <div className="passion-photos-grid">
          {passionPhotos.map((photo, idx) => (
            <div key={idx} className="passion-photo-card">
              <img
                src={photo}
                alt={`Passion ${idx + 1}`}
                className="passion-photo-thumb"
              />
              <button
                type="button"
                className="passion-photo-remove-btn"
                title="Remove photo"
                aria-label={`Remove photo ${idx + 1}`}
                onClick={() => handleRemovePassionPhoto(idx)}
              >
                ×
              </button>
            </div>
          ))}
          {passionPhotos.length < 3 && (
            <label className="passion-photo-add-box" title="Add photo">
              <input
                type="file"
                accept="image/*"
                multiple
                className="visually-hidden"
                onChange={handlePassionPhotoUpload}
              />
              <span className="passion-add-icon">+</span>
              <span className="font-small quiet">Add photo</span>
            </label>
          )}
        </div>
      </div>

      {/* Option to allow or deny viewing profile from chat */}
      <div className="field">
        <label className="profile-privacy-toggle-card">
          <input
            type="checkbox"
            checked={allowProfileView}
            onChange={(e) => setAllowProfileView(e.target.checked)}
          />
          <div className="privacy-toggle-info">
            <strong>Share my profile in conversations</strong>
            <p className="quiet font-small">
              {allowProfileView
                ? 'People you chat with can tap your avatar to view your bio, interests, and passion photos.'
                : 'Private profile: chat partners cannot view your detailed profile.'}
            </p>
          </div>
        </label>
      </div>

      {/* Note d'explication de l'astérisque obligatoire */}
      <p className="required-footnote">
        <span className="required-asterisk">*</span> Mandatory fields
      </p>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button
        type="submit"
        className="button button-primary button-wide"
        disabled={!ready || busy}
      >
        {busy ? 'Joining…' : 'Continue'}
      </button>
    </form>
  )
}

export default JoinForm
