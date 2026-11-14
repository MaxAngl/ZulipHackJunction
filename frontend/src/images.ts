// Lecture et réduction des fichiers choisis par la personne, avant de les envoyer au backend.
// Une photo de téléphone pèse plusieurs Mo : réduite à 800 px en JPEG, elle tient en 100 à 200 Ko.

export function readAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () =>
      typeof reader.result === 'string'
        ? resolve(reader.result)
        : reject(new Error('Unreadable file'))
    reader.onerror = () => reject(reader.error ?? new Error('Unreadable file'))
    reader.readAsDataURL(file)
  })
}

// Image réduite à `maxSide` pixels sur son plus grand côté (jamais agrandie).
export async function shrinkImage(
  dataUrl: string,
  maxSide = 800,
  quality = 0.82,
): Promise<string> {
  const image = new Image()
  image.src = dataUrl
  await image.decode()
  const scale = Math.min(
    1,
    maxSide / Math.max(image.naturalWidth, image.naturalHeight),
  )
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale))
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale))
  const context = canvas.getContext('2d')
  if (!context) return dataUrl
  context.drawImage(image, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/jpeg', quality)
}

// Une image choisie dans un champ fichier, lue puis réduite.
export async function pickedImage(file: File, maxSide = 800): Promise<string> {
  return shrinkImage(await readAsDataUrl(file), maxSide)
}
