
import { useEffect, useState, type FormEvent } from "react"

type Item = {
  id: number
  itemName: string
  itemType: string
  location: string
  date: string
  description: string
  contact: string
  email: string
  image: string
}

const starterItems: Item[] = [
  {
    id: 1,
    itemName: "Black Wallet",
    itemType: "Lost",
    location: "University Cafeteria",
    date: "2026-11-10",
    description: "A black wallet reported missing.",
    contact: "",
    email: "",
    image: ""
  },
  {
    id: 2,
    itemName: "Student ID Card",
    itemType: "Lost",
    location: "Library",
    date: "2026-11-11",
    description: "A student ID card was lost.",
    contact: "",
    email: "",
    image: ""
  }
]

function getSavedItems(): Item[] {
  try {
    return JSON.parse(localStorage.getItem("reportedItems") || "[]")
  } catch {
    return []
  }
}

export default function App() {
  const [items, setItems] = useState<Item[]>(getSavedItems)
  const [itemName, setItemName] = useState("")
  const [itemType, setItemType] = useState("Lost")
  const [location, setLocation] = useState("")
  const [date, setDate] = useState("")
  const [description, setDescription] = useState("")
  const [contact, setContact] = useState("")
  const [email, setEmail] = useState("")
  const [image, setImage] = useState("")

  useEffect(() => {
    localStorage.setItem("reportedItems", JSON.stringify(items))
  }, [items])

  function handleImageChange(file?: File) {
    if (!file) {
      setImage("")
      return
    }

    if (!file.type.startsWith("image/")) {
      alert("Please select an image file.")
      return
    }

    if (file.size > 1024 * 1024) {
      alert("Please choose an image smaller than 1 MB.")
      return
    }

    const reader = new FileReader()
    reader.onload = () => setImage(String(reader.result))
    reader.readAsDataURL(file)
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const newItem: Item = {
      id: Date.now(),
      itemName,
      itemType,
      location,
      date,
      description,
      contact,
      email,
      image
    }

    setItems((previous) => [newItem, ...previous])

    setItemName("")
    setItemType("Lost")
    setLocation("")
    setDate("")
    setDescription("")
    setContact("")
    setEmail("")
    setImage("")

    event.currentTarget.reset()
    alert("Your item has been reported successfully!")
  }

  const allItems = [...items, ...starterItems]

  return (
    <div className="app">
      <nav className="navbar">
        <div className="logo">Campus Lost &amp; Found</div>
        <div className="nav-links">
          <a href="#home">Home</a>
          <a href="#items">Browse Items</a>
          <a href="#report">Report Item</a>
        </div>
      </nav>

      <header id="home" className="hero">
        <h1>Campus Lost &amp; Found</h1>
        <p>Welcome to our campus platform.</p>
        <p>
          Helping students report and find lost items
          around the university campus.
        </p>
      </header>

      <section className="about">
        <h2>About Our Website</h2>
        <p>
          This platform helps students report and find lost
          items on campus. Students can submit item details
          and browse reports shared by others.
        </p>
      </section>

      <section id="items" className="items-section">
        <h2>Recent Lost &amp; Found Items</h2>

        {allItems.length === 0 && (
          <p className="empty-message">No items reported yet.</p>
        )}

        <div className="items-grid">
          {allItems.map((item) => (
            <article className="item-card" key={item.id}>
              <span className={`item-type ${item.itemType.toLowerCase()}`}>
                {item.itemType} Item
              </span>

              <h3>{item.itemName}</h3>
              {item.image && (
                <img className="item-image" src={item.image} alt={item.itemName} />
              )}
              <p><strong>Location:</strong> {item.location}</p>
              <p><strong>Date:</strong> {item.date}</p>
              <p><strong>Description:</strong> {item.description}</p>
              {item.contact && <p><strong>Contact:</strong> {item.contact}</p>}
              {item.email && <p><strong>Email:</strong> {item.email}</p>}
            </article>
          ))}
        </div>
      </section>

      <section className="form-container" id="report">
        <h2>Report an Item</h2>

        <form onSubmit={handleSubmit}>
          <label htmlFor="item-name">Item Name:</label>
          <input
            id="item-name"
            value={itemName}
            onChange={(e) => setItemName(e.target.value)}
            placeholder="Enter item name"
            required
          />

          <label htmlFor="item-type">Item Type:</label>
          <select
            id="item-type"
            value={itemType}
            onChange={(e) => setItemType(e.target.value)}
          >
            <option value="Lost">Lost Item</option>
            <option value="Found">Found Item</option>
          </select>

          <label htmlFor="item-location">Location:</label>
          <input
            id="item-location"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Enter location"
            required
          />

          <label htmlFor="item-date">Date:</label>
          <input
            id="item-date"
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            required
          />

          <label htmlFor="item-description">Description:</label>
          <textarea
            id="item-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the item"
            required
          />

          <label htmlFor="contact-number">Contact Number:</label>
          <input
            id="contact-number"
            value={contact}
            onChange={(e) => setContact(e.target.value)}
            placeholder="Enter contact number"
            required
          />

          <label htmlFor="email-address">Email Address:</label>
          <input
            id="email-address"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Enter email address"
            required
          />

          <label htmlFor="item-image">Item Image:</label>
          <input
            id="item-image"
            type="file"
            accept="image/*"
            onChange={(e) => handleImageChange(e.target.files?.[0])}
          />

          {image && <img className="image-preview" src={image} alt="Selected item" />}

          <button type="submit">Submit Report</button>
        </form>
      </section>

      <footer>
        <p>Campus Lost &amp; Found | Helping students find their belongings</p>
      </footer>
    </div>
  )
}
