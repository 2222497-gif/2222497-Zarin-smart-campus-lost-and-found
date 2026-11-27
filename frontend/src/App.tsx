import { useEffect, useRef, useState, type FormEvent } from "react"

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "")
const ADMIN_USER_PAGE_SIZE = 20

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
  userId: number
  groupId: number | null
}

type ApiItem = {
  id: number
  item_name: string
  item_type: string
  location: string
  date: string
  description: string
  contact: string
  email: string
  image: string | null
  user_id: number
  group_id: number | null
}

type ItemGroup = {
  id: number
  name: string
  description: string
  owner_id: number
  created_at: string
}

type GroupMember = {
  user_id: number
  name: string
  email: string
  created_at: string
}

type CurrentUser = {
  id: number
  name: string
  email: string
  role: string
}

type UserSession = {
  id: number
  created_at: string
  expires_at: string
  revoked_at: string | null
  ip_address: string | null
  user_agent: string | null
}

type AdminUser = {
  id: number
  name: string
  email: string
  role: string
  is_banned: boolean
  created_at: string
}

type LoginAttempt = {
  id: number
  user_id: number | null
  email: string
  success: boolean
  ip_address: string | null
  created_at: string
}

type AuditLog = {
  id: number
  actor_id: number | null
  action: string
  target_type: string
  target_id: number | null
  details: string | null
  created_at: string
}

type AdminStats = {
  total_users: number
  total_items: number
  banned_users: number
  admin_users: number
  lost_items: number
  found_items: number
}

function mapItem(item: ApiItem): Item {
  return {
    id: item.id,
    itemName: item.item_name,
    itemType: item.item_type,
    location: item.location,
    date: item.date,
    description: item.description,
    contact: item.contact,
    email: item.email,
    image: item.image || "",
    userId: item.user_id,
    groupId: item.group_id
  }
}

export default function App() {
  const [items, setItems] = useState<Item[]>([])
  const [token, setToken] = useState(
    localStorage.getItem("access_token") || ""
  )
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [sessions, setSessions] = useState<UserSession[]>([])
  const [groups, setGroups] = useState<ItemGroup[]>([])
  const [groupMembers, setGroupMembers] = useState<
    Record<number, GroupMember[]>
  >({})
  const [groupMemberEmails, setGroupMemberEmails] = useState<
    Record<number, string>
  >({})
  const [newGroupName, setNewGroupName] = useState("")
  const [newGroupDescription, setNewGroupDescription] = useState("")
  const [groupLoading, setGroupLoading] = useState(false)
  const [sessionsLoading, setSessionsLoading] = useState(false)
  const [revokingSessionId, setRevokingSessionId] = useState<number | null>(null)
  const refreshRequest = useRef<Promise<string | null> | null>(null)

  const [authMode, setAuthMode] = useState<"login" | "register">("login")
  const [name, setName] = useState("")
  const [authEmail, setAuthEmail] = useState("")
  const [password, setPassword] = useState("")
  const [authLoading, setAuthLoading] = useState(false)
  const [profileName, setProfileName] = useState("")
  const [profileEmail, setProfileEmail] = useState("")
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [profileLoading, setProfileLoading] = useState(false)
  const [passwordLoading, setPasswordLoading] = useState(false)

  const [search, setSearch] = useState("")
  const [filter, setFilter] = useState("All")
  const [editingId, setEditingId] = useState<number | null>(null)

  const [itemName, setItemName] = useState("")
  const [itemType, setItemType] = useState("Lost")
  const [location, setLocation] = useState("")
  const [date, setDate] = useState("")
  const [description, setDescription] = useState("")
  const [contact, setContact] = useState("")
  const [email, setEmail] = useState("")
  const [image, setImage] = useState("")
  const [selectedGroupId, setSelectedGroupId] = useState("")

  const [activeView, setActiveView] = useState<"home" | "admin">("home")

  const [stats, setStats] = useState<AdminStats | null>(null)
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([])
  const [loginAttempts, setLoginAttempts] = useState<LoginAttempt[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([])
  const [adminSearch, setAdminSearch] = useState("")
  const [roleFilter, setRoleFilter] = useState("All")
  const [statusFilter, setStatusFilter] = useState("All")
  const [adminUserPage, setAdminUserPage] = useState(0)
  const [hasNextAdminUserPage, setHasNextAdminUserPage] = useState(false)
  const [adminLoading, setAdminLoading] = useState(false)

  const isLoggedIn = Boolean(token)
  const isAdmin = currentUser?.role === "admin"

  function clearLocalSession() {
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
    localStorage.removeItem("session_id")
    setToken("")
    setCurrentUser(null)
    setSessions([])
    setActiveView("home")
    resetForm()
  }

  async function refreshAccessToken(): Promise<string | null> {
    if (refreshRequest.current) {
      return refreshRequest.current
    }

    const refreshToken = localStorage.getItem("refresh_token")
    if (!refreshToken) {
      return null
    }

    refreshRequest.current = (async () => {
      try {
        const response = await fetch(`${API_URL}/api/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken })
        })

        if (!response.ok) {
          return null
        }

        const data: {
          access_token: string
          refresh_token: string
          session_id: number
        } = await response.json()

        localStorage.setItem("access_token", data.access_token)
        localStorage.setItem("refresh_token", data.refresh_token)
        localStorage.setItem("session_id", String(data.session_id))
        setToken(data.access_token)
        return data.access_token
      } catch (error) {
        console.error("Refreshing the session failed:", error)
        return null
      } finally {
        refreshRequest.current = null
      }
    })()

    return refreshRequest.current
  }

  async function authenticatedFetch(
    url: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const accessToken = localStorage.getItem("access_token") || token
    if (!accessToken) {
      return fetch(url, options)
    }

    const sendWithToken = (value: string) => {
      const headers = new Headers(options.headers)
      headers.set("Authorization", `Bearer ${value}`)
      return fetch(url, { ...options, headers })
    }

    const response = await sendWithToken(accessToken)
    if (response.status !== 401) {
      return response
    }

    const refreshedToken = await refreshAccessToken()
    if (!refreshedToken) {
      clearLocalSession()
      return response
    }

    return sendWithToken(refreshedToken)
  }

  async function loadSessions() {
    if (!token) {
      setSessions([])
      return
    }

    setSessionsLoading(true)
    try {
      const response = await authenticatedFetch(`${API_URL}/api/sessions`)
      if (!response.ok) {
        throw new Error("Could not load active sessions")
      }
      setSessions(await response.json())
    } catch (error) {
      console.error("Loading sessions failed:", error)
    } finally {
      setSessionsLoading(false)
    }
  }

  async function loadItems() {
    try {
      const response = await authenticatedFetch(`${API_URL}/api/items`)

      if (!response.ok) {
        throw new Error("Could not load items")
      }

      const data: ApiItem[] = await response.json()
      setItems(data.map(mapItem))
    } catch (error) {
      console.error("Loading items failed:", error)
    }
  }

  async function loadGroups() {
    if (!token) {
      setGroups([])
      setGroupMembers({})
      return
    }

    try {
      const response = await authenticatedFetch(`${API_URL}/api/groups`)
      if (!response.ok) {
        throw new Error("Could not load groups")
      }

      const data: ItemGroup[] = await response.json()
      setGroups(data)
      const ownedGroups = data.filter(
        (group) => group.owner_id === currentUser?.id
      )
      const memberLists = await Promise.all(
        ownedGroups.map(async (group) => {
          const membersResponse = await authenticatedFetch(
            `${API_URL}/api/groups/${group.id}/members`
          )
          if (!membersResponse.ok) {
            throw new Error("Could not load group members")
          }
          return [group.id, await membersResponse.json() as GroupMember[]] as const
        })
      )
      setGroupMembers(Object.fromEntries(memberLists))
    } catch (error) {
      console.error("Loading groups failed:", error)
    }
  }

  async function handleCreateGroup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setGroupLoading(true)

    try {
      const response = await authenticatedFetch(`${API_URL}/api/groups`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newGroupName,
          description: newGroupDescription
        })
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || "Could not create group")
      }

      setNewGroupName("")
      setNewGroupDescription("")
      await loadGroups()
      alert("Group created successfully.")
    } catch (error) {
      alert(error instanceof Error ? error.message : "Could not create group")
    } finally {
      setGroupLoading(false)
    }
  }

  async function updateGroup(group: ItemGroup) {
    const name = window.prompt("Group name", group.name)
    if (name === null) return
    const description = window.prompt("Group description", group.description)
    if (description === null) return

    try {
      const response = await authenticatedFetch(
        `${API_URL}/api/groups/${group.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, description })
        }
      )
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || "Could not update group")
      }

      await loadGroups()
      alert("Group settings updated.")
    } catch (error) {
      alert(error instanceof Error ? error.message : "Could not update group")
    }
  }

  async function archiveGroup(group: ItemGroup) {
    if (!window.confirm(
      `Archive "${group.name}"? Its item records will be preserved but group access will end.`
    )) {
      return
    }

    try {
      const response = await authenticatedFetch(
        `${API_URL}/api/groups/${group.id}`,
        {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirm: true })
        }
      )
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || "Could not archive group")
      }

      await Promise.all([loadGroups(), loadItems()])
      alert(data.message || "Group archived.")
    } catch (error) {
      alert(error instanceof Error ? error.message : "Could not archive group")
    }
  }

  async function addGroupMember(
    event: FormEvent<HTMLFormElement>,
    groupId: number
  ) {
    event.preventDefault()
    const email = groupMemberEmails[groupId]?.trim()
    if (!email) return

    try {
      const response = await authenticatedFetch(
        `${API_URL}/api/groups/${groupId}/members`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email })
        }
      )
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || "Could not add group member")
      }

      setGroupMemberEmails((previous) => ({ ...previous, [groupId]: "" }))
      await loadGroups()
      alert("Group member added.")
    } catch (error) {
      alert(error instanceof Error ? error.message : "Could not add member")
    }
  }

  async function removeGroupMember(groupId: number, member: GroupMember) {
    if (!window.confirm(`Remove ${member.name} from this group?`)) {
      return
    }

    try {
      const response = await authenticatedFetch(
        `${API_URL}/api/groups/${groupId}/members/${member.user_id}`,
        { method: "DELETE" }
      )
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.detail || "Could not remove group member")
      }

      await loadGroups()
      alert("Group member removed. Their item records were preserved.")
    } catch (error) {
      alert(error instanceof Error ? error.message : "Could not remove member")
    }
  }

  async function loadCurrentUser() {
    if (!token) {
      setCurrentUser(null)
      return
    }

    try {
      const response = await authenticatedFetch(`${API_URL}/api/me`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      })

      if (!response.ok) {
        throw new Error("Session expired. Please login again.")
      }

      const data: CurrentUser = await response.json()
      setCurrentUser(data)
    } catch (error) {
      clearLocalSession()

      if (error instanceof Error) {
        alert(error.message)
      }
    }
  }

  useEffect(() => {
    loadItems()
  }, [token])

  useEffect(() => {
    loadCurrentUser()
  }, [token])

  useEffect(() => {
    loadSessions()
  }, [token])

  useEffect(() => {
    loadGroups()
  }, [token, currentUser?.id])

  useEffect(() => {
    if (currentUser) {
      setProfileName(currentUser.name)
      setProfileEmail(currentUser.email)
    }
  }, [currentUser])

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAuthLoading(true)

    try {
      const register = authMode === "register"

      const response = await fetch(
        `${API_URL}${register ? "/api/register" : "/api/login"}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(
            register
              ? { name, email: authEmail, password }
              : { email: authEmail, password }
          )
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Authentication failed")
      }

      if (register) {
        alert("Registration successful! Please login.")
        setAuthMode("login")
        setPassword("")
      } else {
        localStorage.setItem("access_token", data.access_token)
        localStorage.setItem("refresh_token", data.refresh_token)
        localStorage.setItem("session_id", String(data.session_id))
        setToken(data.access_token)
        setPassword("")
        alert("Login successful!")
      }
    } catch (error) {
      alert(
        error instanceof Error
          ? error.message
          : "Something went wrong"
      )
    } finally {
      setAuthLoading(false)
    }
  }

  async function handleProfileUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setProfileLoading(true)

    try {
      const response = await authenticatedFetch(`${API_URL}/api/me`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          name: profileName,
          email: profileEmail
        })
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Could not update profile")
      }

      setCurrentUser(data)
      alert("Profile updated successfully.")
    } catch (error) {
      alert(error instanceof Error ? error.message : "Profile update failed")
    } finally {
      setProfileLoading(false)
    }
  }

  async function handlePasswordChange(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPasswordLoading(true)

    try {
      const response = await authenticatedFetch(`${API_URL}/api/me/password`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Could not change password")
      }

      setCurrentPassword("")
      setNewPassword("")
      alert(data.message || "Password changed successfully.")
    } catch (error) {
      alert(error instanceof Error ? error.message : "Password change failed")
    } finally {
      setPasswordLoading(false)
    }
  }

  async function logout() {
    const refreshToken = localStorage.getItem("refresh_token")

    try {
      if (refreshToken) {
        const response = await fetch(`${API_URL}/api/logout`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refreshToken })
        })
        if (!response.ok) {
          throw new Error("The server could not revoke this session.")
        }
      }

      clearLocalSession()
      alert("Logged out successfully.")
    } catch (error) {
      alert(
        error instanceof Error
          ? `Logout failed: ${error.message}`
          : "Logout failed. Please try again."
      )
    }
  }

  function handleImageChange(file?: File) {
    if (!file) {
      setImage("")
      return
    }

    if (!file.type.startsWith("image/") || file.size > 1024 * 1024) {
      alert("Choose an image smaller than 1 MB.")
      return
    }

    const reader = new FileReader()

    reader.onload = () => {
      setImage(String(reader.result))
    }

    reader.readAsDataURL(file)
  }

  function resetForm() {
    setItemName("")
    setItemType("Lost")
    setLocation("")
    setDate("")
    setDescription("")
    setContact("")
    setEmail("")
    setImage("")
    setSelectedGroupId("")
    setEditingId(null)

    const fileInput = document.getElementById(
      "item-image"
    ) as HTMLInputElement | null

    if (fileInput) {
      fileInput.value = ""
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!token) {
      alert("Please login first to report an item.")
      return
    }

    const editing = editingId !== null

    try {
      const response = await authenticatedFetch(
        `${API_URL}/api/items${editing ? `/${editingId}` : ""}`,
        {
          method: editing ? "PUT" : "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            item_name: itemName,
            item_type: itemType,
            location,
            date,
            description,
            contact,
            email,
            image: image || null,
            ...(editing
              ? {}
              : {
                  group_id: selectedGroupId
                    ? Number(selectedGroupId)
                    : null
                })
          })
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Could not save item")
      }

      resetForm()
      await loadItems()

      alert(
        editing
          ? "Item updated successfully!"
          : "Item reported successfully!"
      )
    } catch (error) {
      alert(
        error instanceof Error
          ? error.message
          : "Something went wrong"
      )
    }
  }

  function startEdit(item: Item) {
    setEditingId(item.id)
    setItemName(item.itemName)
    setItemType(item.itemType)
    setLocation(item.location)
    setDate(item.date)
    setDescription(item.description)
    setContact(item.contact)
    setEmail(item.email)
    setImage(item.image)
    setSelectedGroupId(item.groupId ? String(item.groupId) : "")

    document.getElementById("report")?.scrollIntoView({
      behavior: "smooth"
    })
  }

  async function deleteItem(id: number) {
    if (!window.confirm("Are you sure you want to delete this item?")) {
      return
    }

    try {
      const response = await authenticatedFetch(`${API_URL}/api/items/${id}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`
        }
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Could not delete item")
      }

      await loadItems()
      alert("Item deleted successfully.")
    } catch (error) {
      alert(
        error instanceof Error
          ? error.message
          : "Something went wrong"
      )
    }
  }

  async function loadAdminData() {
    if (!token || !isAdmin) return

    setAdminLoading(true)

    try {
      const headers = {
        Authorization: `Bearer ${token}`
      }
      const userQuery = new URLSearchParams({
        skip: String(adminUserPage * ADMIN_USER_PAGE_SIZE),
        limit: String(ADMIN_USER_PAGE_SIZE + 1)
      })

      if (adminSearch.trim()) {
        userQuery.set("search", adminSearch.trim())
      }
      if (roleFilter !== "All") {
        userQuery.set("role", roleFilter)
      }
      if (statusFilter !== "All") {
        userQuery.set("banned", String(statusFilter === "Banned"))
      }

      const endpoints = [
        "/api/admin/stats",
        `/api/admin/users?${userQuery.toString()}`,
        "/api/admin/login-attempts",
        "/api/admin/audit-logs"
      ]

      const responses = await Promise.all(
        endpoints.map(endpoint =>
          authenticatedFetch(`${API_URL}${endpoint}`, { headers })
        )
      )

      const failedIndex = responses.findIndex(
        response => !response.ok
      )

      if (failedIndex !== -1) {
        const failedResponse = responses[failedIndex]
        const errorText = await failedResponse.text()

        throw new Error(
          `${endpoints[failedIndex]} returned ${failedResponse.status}: ${errorText}`
        )
      }

      const [statsData, usersData, attemptsData, logsData] =
        await Promise.all(responses.map(response => response.json()))

      setStats(statsData)
      setAdminUsers(usersData.slice(0, ADMIN_USER_PAGE_SIZE))
      setHasNextAdminUserPage(usersData.length > ADMIN_USER_PAGE_SIZE)
      setLoginAttempts(attemptsData)
      setAuditLogs(logsData)
    } catch (error) {
      alert(
        error instanceof Error
          ? error.message
          : "Could not load admin dashboard"
      )
    } finally {
      setAdminLoading(false)
    }
  }

  useEffect(() => {
    if (activeView === "admin" && isAdmin) {
      const timeout = window.setTimeout(loadAdminData, 250)
      return () => window.clearTimeout(timeout)
    }
  }, [
    activeView,
    isAdmin,
    token,
    adminSearch,
    roleFilter,
    statusFilter,
    adminUserPage
  ])

  async function updateUserRole(userId: number, role: string) {
    if (!window.confirm(`Change this user's role to ${role}?`)) return

    try {
      const response = await authenticatedFetch(
        `${API_URL}/api/admin/users/${userId}/role`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({ role })
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Could not update user role")
      }

      alert(data.message || "User role updated.")
      await loadAdminData()
    } catch (error) {
      alert(error instanceof Error ? error.message : "Something went wrong")
    }
  }

  async function changeBanStatus(user: AdminUser) {
    const action = user.is_banned ? "unban" : "ban"

    if (!window.confirm(`Are you sure you want to ${action} ${user.name}?`)) {
      return
    }

    try {
      const response = await authenticatedFetch(
        `${API_URL}/api/admin/users/${user.id}/${action}`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      )

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || `Could not ${action} user`)
      }

      alert(data.message || `User ${action}ned successfully.`)
      await loadAdminData()
    } catch (error) {
      alert(error instanceof Error ? error.message : "Something went wrong")
    }
  }

  async function exportAuditLogs() {
    try {
      const response = await authenticatedFetch(
        `${API_URL}/api/admin/audit-logs/export`,
        {
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      )

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || "Could not export audit logs")
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement("a")

      link.href = url
      link.download = "audit_logs.csv"
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (error) {
      alert(error instanceof Error ? error.message : "Export failed")
    }
  }

  async function revokeSession(sessionId: number) {
    setRevokingSessionId(sessionId)

    try {
      const response = await authenticatedFetch(
        `${API_URL}/api/sessions/${sessionId}`,
        { method: "DELETE" }
      )
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Could not revoke session")
      }

      if (String(sessionId) === localStorage.getItem("session_id")) {
        clearLocalSession()
        alert("This session was revoked.")
        return
      }

      await loadSessions()
      alert("Session revoked successfully.")
    } catch (error) {
      alert(error instanceof Error ? error.message : "Session revocation failed")
    } finally {
      setRevokingSessionId(null)
    }
  }

  const visibleItems = items.filter((item) => {
    const searchableText =
      `${item.itemName} ${item.location} ${item.description}`

    const matchesSearch = searchableText
      .toLowerCase()
      .includes(search.toLowerCase())

    const matchesType =
      filter === "All" || item.itemType === filter

    return matchesSearch && matchesType
  })

  return (
    <div className="app">
      <nav className="navbar">
        <div className="logo">Campus Lost &amp; Found</div>

        <div className="nav-links">
          <a href="#home" onClick={() => setActiveView("home")}>Home</a>
          <a href="#items" onClick={() => setActiveView("home")}>Browse Items</a>
          <a href="#report" onClick={() => setActiveView("home")}>Report Item</a>
          <a href="#account" onClick={() => setActiveView("home")}>
            {isLoggedIn ? "Account" : "Login"}
          </a>

          {isAdmin && (
            <button
              type="button"
              onClick={() => setActiveView("admin")}
            >
              Admin Dashboard
            </button>
          )}

          {isLoggedIn && (
            <button type="button" onClick={logout}>
              Logout
            </button>
          )}
        </div>
      </nav>

      {activeView === "admin" && isAdmin ? (
        <main className="admin-dashboard">
          <h1>Admin Dashboard</h1>
          <p>Manage users and monitor platform activity.</p>

          <button type="button" onClick={() => setActiveView("home")}>
            Back to Website
          </button>

          <button
            type="button"
            onClick={loadAdminData}
            disabled={adminLoading}
          >
            {adminLoading ? "Loading..." : "Refresh Dashboard"}
          </button>

          {adminLoading && <p>Loading admin information...</p>}

          {stats && (
            <section className="admin-stats">
              <h2>Platform Statistics</h2>
              <div className="items-grid">
                <article className="item-card">
                  <h3>Total Users</h3>
                  <p>{stats.total_users}</p>
                </article>
                <article className="item-card">
                  <h3>Total Items</h3>
                  <p>{stats.total_items}</p>
                </article>
                <article className="item-card">
                  <h3>Administrators</h3>
                  <p>{stats.admin_users}</p>
                </article>
                <article className="item-card">
                  <h3>Banned Users</h3>
                  <p>{stats.banned_users}</p>
                </article>
                <article className="item-card">
                  <h3>Lost Items</h3>
                  <p>{stats.lost_items}</p>
                </article>
                <article className="item-card">
                  <h3>Found Items</h3>
                  <p>{stats.found_items}</p>
                </article>
              </div>
            </section>
          )}

          <section className="admin-users">
            <h2>User Management</h2>

            <input
              type="text"
              placeholder="Search users by name or email..."
              value={adminSearch}
              onChange={(e) => {
                setAdminSearch(e.target.value)
                setAdminUserPage(0)
              }}
            />

            <select
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value)
                setAdminUserPage(0)
              }}
            >
              <option value="All">All Roles</option>
              <option value="user">Users</option>
              <option value="admin">Admins</option>
            </select>

            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setAdminUserPage(0)
              }}
            >
              <option value="All">All Statuses</option>
              <option value="Active">Active</option>
              <option value="Banned">Banned</option>
            </select>

            <p>
              Showing {adminUsers.length} users on page {adminUserPage + 1}
            </p>

            <div className="items-grid">
              {adminUsers.map((user) => (
                <article className="item-card" key={user.id}>
                  <h3>{user.name}</h3>
                  <p>{user.email}</p>
                  <p>User ID: {user.id}</p>
                  <p>Role: {user.role}</p>
                  <p>Status: {user.is_banned ? "Banned" : "Active"}</p>
                  <p>
                    Joined: {new Date(user.created_at).toLocaleDateString()}
                  </p>

                  <label htmlFor={`role-${user.id}`}>Change Role:</label>
                  <select
                    id={`role-${user.id}`}
                    value={user.role}
                    disabled={user.id === currentUser?.id}
                    onChange={(e) =>
                      updateUserRole(user.id, e.target.value)
                    }
                  >
                    <option value="user">User</option>
                    <option value="admin">Admin</option>
                  </select>

                  <button
                    type="button"
                    disabled={user.id === currentUser?.id}
                    onClick={() => changeBanStatus(user)}
                  >
                    {user.is_banned ? "Unban User" : "Ban User"}
                  </button>
                </article>
              ))}
            </div>

            {adminUsers.length === 0 && !adminLoading && (
              <p>No users match these filters.</p>
            )}

            <div className="admin-pagination" aria-label="User list pages">
              <button
                type="button"
                disabled={adminUserPage === 0 || adminLoading}
                onClick={() => setAdminUserPage(page => page - 1)}
              >
                Previous
              </button>
              <span>Page {adminUserPage + 1}</span>
              <button
                type="button"
                disabled={!hasNextAdminUserPage || adminLoading}
                onClick={() => setAdminUserPage(page => page + 1)}
              >
                Next
              </button>
            </div>
          </section>

          <section className="admin-activity">
            <h2>Login Attempts</h2>

            {loginAttempts.length === 0 ? (
              <p>No login attempts recorded.</p>
            ) : (
              <div className="items-grid">
                {loginAttempts.map((attempt) => (
                  <article className="item-card" key={attempt.id}>
                    <p><strong>Email:</strong> {attempt.email}</p>
                    <p>
                      <strong>Result:</strong>{" "}
                      {attempt.success ? "Successful" : "Failed"}
                    </p>
                    <p><strong>User ID:</strong> {attempt.user_id ?? "Unknown"}</p>
                    <p><strong>IP:</strong> {attempt.ip_address || "Unavailable"}</p>
                    <p>
                      <strong>Time:</strong>{" "}
                      {new Date(attempt.created_at).toLocaleString()}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </section>

          <section className="admin-activity">
            <h2>Audit Logs</h2>

            <button type="button" onClick={exportAuditLogs}>
              Export Audit Logs (CSV)
            </button>

            {auditLogs.length === 0 ? (
              <p>No audit logs recorded.</p>
            ) : (
              <div className="items-grid">
                {auditLogs.map((log) => (
                  <article className="item-card" key={log.id}>
                    <p><strong>Action:</strong> {log.action}</p>
                    <p><strong>Actor ID:</strong> {log.actor_id ?? "System"}</p>
                    <p><strong>Target:</strong> {log.target_type}</p>
                    <p><strong>Target ID:</strong> {log.target_id ?? "N/A"}</p>
                    <p><strong>Details:</strong> {log.details || "N/A"}</p>
                    <p>
                      <strong>Time:</strong>{" "}
                      {new Date(log.created_at).toLocaleString()}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </section>
        </main>
      ) : (
        <>
          <header id="home" className="hero">
            <h1>Campus Lost &amp; Found</h1>
            <p>Welcome to our campus platform.</p>
            <p>
              Helping students report and find lost items around
              the university campus.
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

            <input
              type="text"
              placeholder="Search by item name, location or description..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />

            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="All">All Items</option>
              <option value="Lost">Lost Items</option>
              <option value="Found">Found Items</option>
            </select>

            {visibleItems.length === 0 && (
              <p className="empty-message">
                No matching items found.
              </p>
            )}

            <div className="items-grid">
              {visibleItems.map((item) => (
                <article className="item-card" key={item.id}>
                  <span
                    className={`item-type ${item.itemType.toLowerCase()}`}
                  >
                    {item.itemType} Item
                  </span>

                  <h3>{item.itemName}</h3>

                  {item.image && (
                    <img
                      className="item-image"
                      src={item.image}
                      alt={item.itemName}
                    />
                  )}

                  <p><strong>Location:</strong> {item.location}</p>
                  <p><strong>Date:</strong> {item.date}</p>
                  <p><strong>Description:</strong> {item.description}</p>
                  <p><strong>Contact:</strong> {item.contact}</p>
                  <p><strong>Email:</strong> {item.email}</p>
                  {item.groupId !== null && (
                    <p>
                      <strong>Group:</strong>{" "}
                      {groups.find((group) => group.id === item.groupId)?.name
                        || "Shared group"}
                    </p>
                  )}

                  {isLoggedIn && (
                    currentUser?.id === item.userId
                    || groups.some(
                      (group) =>
                        group.id === item.groupId
                        && group.owner_id === currentUser?.id
                    )
                  ) && (
                    <div>
                      <button
                        type="button"
                        onClick={() => startEdit(item)}
                      >
                        Edit
                      </button>

                      <button
                        type="button"
                        onClick={() => deleteItem(item.id)}
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>

          <section id="account" className="form-container">
            <h2>
              {isLoggedIn
                ? "Your Account"
                : authMode === "login"
                  ? "Login"
                  : "Create Account"}
            </h2>

            {isLoggedIn ? (
              <div className="profile-panel">
                <div className="profile-summary">
                  <div className="avatar" aria-hidden="true">
                    {(currentUser?.name || "U").charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <p className="profile-name">{currentUser?.name || "User"}</p>
                    <p>{currentUser?.email}</p>
                    <span className="role-badge">{currentUser?.role}</span>
                  </div>
                </div>

                <form onSubmit={handleProfileUpdate} className="profile-form">
                  <h3>Profile details</h3>
                  <label htmlFor="profile-name">Full Name</label>
                  <input
                    id="profile-name"
                    type="text"
                    value={profileName}
                    onChange={(e) => setProfileName(e.target.value)}
                    minLength={2}
                    required
                  />

                  <label htmlFor="profile-email">Email Address</label>
                  <input
                    id="profile-email"
                    type="email"
                    value={profileEmail}
                    onChange={(e) => setProfileEmail(e.target.value)}
                    required
                  />

                  <button type="submit" disabled={profileLoading}>
                    {profileLoading ? "Saving..." : "Save Profile"}
                  </button>
                </form>

                <form onSubmit={handlePasswordChange} className="profile-form">
                  <h3>Change password</h3>
                  <label htmlFor="current-password">Current Password</label>
                  <input
                    id="current-password"
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    required
                  />

                  <label htmlFor="new-password">New Password</label>
                  <input
                    id="new-password"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    minLength={8}
                    required
                  />

                  <button type="submit" disabled={passwordLoading}>
                    {passwordLoading ? "Updating..." : "Change Password"}
                  </button>
                </form>

                <section className="profile-form" aria-labelledby="sessions-heading">
                  <h3 id="sessions-heading">Sessions</h3>
                  {sessionsLoading ? (
                    <p>Loading sessions...</p>
                  ) : sessions.length === 0 ? (
                    <p>No sessions found.</p>
                  ) : (
                    <ul>
                      {sessions.map((session) => {
                        const isCurrentSession =
                          String(session.id) ===
                          localStorage.getItem("session_id")

                        return (
                          <li key={session.id}>
                            <p>
                              {isCurrentSession ? "This session" : "Session"}{" "}
                              &middot; Started{" "}
                              {new Date(session.created_at).toLocaleString()}
                            </p>
                            <p>
                              {session.user_agent || "Unknown device"}
                              {session.ip_address
                                ? ` | ${session.ip_address}`
                                : ""}
                            </p>
                            {session.revoked_at ? (
                              <p>Revoked</p>
                            ) : (
                              <button
                                type="button"
                                disabled={revokingSessionId === session.id}
                                onClick={() => revokeSession(session.id)}
                              >
                                {revokingSessionId === session.id
                                  ? "Revoking..."
                                  : "Revoke session"}
                              </button>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </section>

                <section className="profile-form" aria-labelledby="groups-heading">
                  <h3 id="groups-heading">Groups</h3>
                  <p>
                    Members can view and create group items, and edit or delete
                    their own. Owners can manage all group items, settings, and
                    membership.
                  </p>

                  <form onSubmit={handleCreateGroup}>
                    <label htmlFor="new-group-name">Group name</label>
                    <input
                      id="new-group-name"
                      value={newGroupName}
                      onChange={(event) => setNewGroupName(event.target.value)}
                      minLength={2}
                      maxLength={100}
                      required
                    />
                    <label htmlFor="new-group-description">Description</label>
                    <textarea
                      id="new-group-description"
                      value={newGroupDescription}
                      onChange={(event) =>
                        setNewGroupDescription(event.target.value)
                      }
                      maxLength={1000}
                    />
                    <button type="submit" disabled={groupLoading}>
                      {groupLoading ? "Creating..." : "Create Group"}
                    </button>
                  </form>

                  {groups.length === 0 ? (
                    <p>You are not a member of any groups.</p>
                  ) : (
                    <div className="items-grid">
                      {groups.map((group) => {
                        const isGroupOwner =
                          group.owner_id === currentUser?.id
                        const members = groupMembers[group.id] || []

                        return (
                          <article className="item-card" key={group.id}>
                            <h4>{group.name}</h4>
                            <p>{group.description || "No description"}</p>
                            <p>{isGroupOwner ? "Owner" : "Member"}</p>

                            {isGroupOwner && (
                              <>
                                <button
                                  type="button"
                                  onClick={() => updateGroup(group)}
                                >
                                  Edit Group Settings
                                </button>
                                <button
                                  type="button"
                                  onClick={() => archiveGroup(group)}
                                >
                                  Archive Group
                                </button>

                                <form
                                  onSubmit={(event) =>
                                    addGroupMember(event, group.id)
                                  }
                                >
                                  <label htmlFor={`member-email-${group.id}`}>
                                    Add member by email
                                  </label>
                                  <input
                                    id={`member-email-${group.id}`}
                                    type="email"
                                    value={groupMemberEmails[group.id] || ""}
                                    onChange={(event) =>
                                      setGroupMemberEmails((previous) => ({
                                        ...previous,
                                        [group.id]: event.target.value
                                      }))
                                    }
                                    required
                                  />
                                  <button type="submit">Add Member</button>
                                </form>

                                <h5>Members</h5>
                                {members.length === 0 ? (
                                  <p>No members added yet.</p>
                                ) : (
                                  <ul>
                                    {members.map((member) => (
                                      <li key={member.user_id}>
                                        {member.name} ({member.email})
                                        <button
                                          type="button"
                                          onClick={() =>
                                            removeGroupMember(group.id, member)
                                          }
                                        >
                                          Remove
                                        </button>
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </>
                            )}
                          </article>
                        )
                      })}
                    </div>
                  )}
                </section>

                <button type="button" className="secondary-button" onClick={logout}>
                  Logout
                </button>
              </div>
            ) : (
              <>
                <form onSubmit={handleAuth}>
                  {authMode === "register" && (
                    <>
                      <label htmlFor="auth-name">Full Name:</label>
                      <input
                        id="auth-name"
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                      />
                    </>
                  )}

                  <label htmlFor="auth-email">Email:</label>
                  <input
                    id="auth-email"
                    type="email"
                    value={authEmail}
                    onChange={(e) => setAuthEmail(e.target.value)}
                    required
                  />

                  <label htmlFor="auth-password">Password:</label>
                  <input
                    id="auth-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />

                  <button type="submit" disabled={authLoading}>
                    {authLoading
                      ? authMode === "login" ? "Signing in..." : "Creating account..."
                      : authMode === "login" ? "Login" : "Register"}
                  </button>
                </form>

                <p>
                  {authMode === "login"
                    ? "Don't have an account?"
                    : "Already have an account?"}

                  <button
                    type="button"
                    onClick={() =>
                      setAuthMode(
                        authMode === "login" ? "register" : "login"
                      )
                    }
                  >
                    {authMode === "login" ? "Register" : "Login"}
                  </button>
                </p>
              </>
            )}
          </section>

          <section className="form-container" id="report">
            <h2>
              {editingId !== null ? "Edit Report" : "Report an Item"}
            </h2>

            {!isLoggedIn && (
              <p>Please login before submitting your report.</p>
            )}

            <form onSubmit={handleSubmit}>
              <label htmlFor="item-name">Item Name:</label>
              <input
                id="item-name"
                type="text"
                value={itemName}
                onChange={(e) => setItemName(e.target.value)}
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
                type="text"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
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
                required
              />

              <label htmlFor="contact-number">Contact Number:</label>
              <input
                id="contact-number"
                type="tel"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                required
              />

              <label htmlFor="item-email">Email Address:</label>
              <input
                id="item-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />

              {isLoggedIn && (
                <>
                  <label htmlFor="item-group">Share with group:</label>
                  <select
                    id="item-group"
                    value={selectedGroupId}
                    onChange={(event) => setSelectedGroupId(event.target.value)}
                    disabled={editingId !== null}
                  >
                    <option value="">Public report</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </>
              )}

              <label htmlFor="item-image">Item Image:</label>
              <input
                id="item-image"
                type="file"
                accept="image/*"
                onChange={(e) =>
                  handleImageChange(e.target.files?.[0])
                }
              />

              {image && (
                <img
                  className="image-preview"
                  src={image}
                  alt="Image Preview"
                />
              )}

              <button type="submit">
                {editingId !== null ? "Save Changes" : "Submit Report"}
              </button>

              {editingId !== null && (
                <button type="button" onClick={resetForm}>
                  Cancel Edit
                </button>
              )}
            </form>
          </section>
        </>
      )}

      <footer>
        <p>
          Campus Lost &amp; Found | Helping students find their belongings
        </p>
      </footer>
    </div>
  )
}