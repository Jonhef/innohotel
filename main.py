from aiohttp import web
import aiosqlite
import os
import hashlib
import asyncio
import datetime
import json

routes = web.RouteTableDef()

def hashpass(a):
    return hashlib.sha256(a.encode()).hexdigest().encode()

@routes.get('/login')
async def login(request: web.Request):
    return web.FileResponse("htmls/login.html")

async def get_role(username, password):
    async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute("SELECT role FROM users WHERE username=(?) AND passwordhash=(?)", 
                            [
                                username, 
                                hashpass(password)
                        ])
            f = await cur.fetchone()
    return (None if f == None else f[0])

async def check(request, roles: tuple):
    if (request.cookies.get("username") == None or request.cookies.get("password") == None):
        return None in roles
    role = await get_role(request.cookies.get("username"), request.cookies.get("password"))
    return role in roles

@routes.post('/signin')
async def signin(request: web.Request):
    try:
        data = await request.json()
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute("SELECT * FROM users WHERE username=(?) AND passwordhash=(?)", 
                                [data["user"], hashlib.sha256(data["pass"].encode()).hexdigest().encode()])
            f = await cur.fetchone()
            resp = web.StreamResponse()
            if (f != None):
                resp.set_cookie("username", data["user"], max_age=12*60*60)
                resp.set_cookie("password", data["pass"], max_age=12*60*60)
                code = 200
            else:
                code = 401
        resp.set_status(code)
        await resp.prepare(request)
        await resp.write(('{"status":"' + str(code) + '"}').encode())
        return resp
    except Exception as e:
        return web.Response(body=str(e), status=500)
    
@routes.get("/signout")
async def signout(request: web.Request):
    try:
        resp = web.HTTPFound("/login")
        resp.del_cookie("username")
        resp.del_cookie("password")
        await resp.prepare(request)
        return resp
    except Exception as e:
        return web.Response(body=str(e), status=500)

@routes.get("/main")
async def mainpage(request: web.Request):
    try:
        async with aiosqlite.connect("database.sqlite3") as db:
            try:
                cur = await db.execute("SELECT role FROM users WHERE username=(?) AND passwordhash=(?)", 
                                [
                                    request.cookies.get("username"), 
                                    hashlib.sha256(request.cookies.get("password").encode())
                                    .hexdigest().encode()
                            ])
                f = await cur.fetchone()
            except:
                resp = web.HTTPFound("/login")
                resp.del_cookie("username")
                resp.del_cookie("password")
                await resp.prepare(request)
                return resp
        if (f == None):
            resp = web.HTTPFound("/login")
            resp.del_cookie("username")
            resp.del_cookie("password")
            await resp.prepare(request)
            return resp
        if (f[0] == 2):
            resp = web.FileResponse("htmls/adminmain.html")
        if (f[0] == 1):
            resp = web.FileResponse("htmls/sysmain.html")
        if (f[0] == 0):
            resp = web.FileResponse("htmls/main.html")
        return resp
    except Exception as e:
        return web.Response(body=str(e), status=500)

@routes.post("/adduser")
async def adduser(request: web.Request):
    if (not (await check(request, (2, )))):
        return web.Response(status=401)
    try:
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute("SELECT role FROM users WHERE username=(?) AND passwordhash=(?)", 
                            [
                                request.cookies.get("username"), 
                                hashpass(request.cookies.get("password"))
                        ])
            f = await cur.fetchone()
        if (f == None):
            resp = web.StreamResponse(status=401)
            resp.del_cookie("username")
            resp.del_cookie("password")
            await resp.prepare(request)
            await resp.write('{"status":"401"}')
        if (f[0] == 1 or f[0] == 0):
            resp = web.StreamResponse(403)
            await resp.prepare(request)
            await resp.write('{"status":"403"}')
        elif (f[0] == 2):
            resp = web.StreamResponse(status=200)
            json = await request.json()
            async with aiosqlite.connect("database.sqlite3") as db:
                await db.execute("INSERT INTO users(username, passwordhash, role, name, id) VALUES((?), (?), (?), (?), (SELECT MAX(ID)+1 FROM users))", 
                                [json["user"], hashpass(json["pass"]), int(json["role"]), json["name"]])
                await db.commit()
            async with aiosqlite.connect("database.sqlite3") as db:
                cur = await db.execute("SELECT id FROM users WHERE username=(?) AND passwordhash=(?) AND role=(?) AND name=(?)",
                                    [json["user"], hashpass(json["pass"]), int(json["role"]), json["name"]])
                id = (await cur.fetchone())[0]
            resp.set_status(status = 200, reason = (f"Done!\nID:{id}").encode())
            await resp.prepare(request)
        return resp
    except Exception as e:
        return web.Response(body=str(e), status=500)

@routes.post("/addroom")
async def addroom(request: web.Request):
    if (not (await check(request, (2, 1)))):
        return web.Response(status=401)
    try:
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute("SELECT role FROM users WHERE username=(?) AND passwordhash=(?)",
                                [
                                    request.cookies.get("username"),
                                    hashpass(request.cookies.get("password"))
                                ])
            f = await cur.fetchone()
            f = f[0]
        if (f == 0):
            resp = web.StreamResponse(403)
            await resp.prepare(request)
            await resp.write('{"status":"403"}')
            return resp
        data = await request.json()
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute("SELECT * FROM rooms WHERE number=(?)", 
                                [int(data["number"])])
            f = await cur.fetchone()
            if (f != None):
                resp = web.StreamResponse(status = 400)
                resp.set_status(400, "This room already exists, delete it before add new")
                return resp
            await db.execute("INSERT INTO rooms(number, isbusy, luxurylevel, numberofguests, floor, comments, priceforanight) VALUES((?), (?), (?), (?), (?), (?), (?))", 
                                [
                                    int(data["number"]),
                                    int(data["isbusy"]),
                                    int(data["luxurylevel"]),
                                    int(data["numberofguests"]),
                                    int(data["floor"]),
                                    data["comments"],
                                    int(data["priceforanight"])
                                ])
            await db.commit()
        return web.Response(body=str(data))
    except Exception as e:
        return web.Response(body=str(e), status=500)
        
@routes.post("/delroom")
async def delroom(request: web.Request):
    if (not (await check(request, (2, 1, )))):
        return web.Response(status=401)
    try:
        async with aiosqlite.connect("database.sqlite3") as db:
            await db.execute("DELETE FROM rooms WHERE number=(?)", 
                            [
                                int((await request.json())["number"])
                            ])
            await db.commit()
        return web.Response()
    except Exception as e:
        return web.Response(body=str(e), status=500)
        
@routes.post("/editroom")
async def editroom(request: web.Request):
    if (not (await check(request, (2, 1, )))):
        return web.Response(status=401)
    try:
        execution = f"""UPDATE rooms
        SET """
        data = await request.json()
        values = []
        for key in data:
            value = data[key]
            if key.find("-old") != -1:
                continue
            execution += f"{key}=(?) "
            values.append(value)
        execution += f"\nWHERE number=(?)"
        values.append(data["number-old"])
        async with aiosqlite.connect("database.sqlite3") as db:
            await db.execute(execution, values)
            await db.commit()
        return web.Response()
    except Exception as e:
        return web.Response(body=str(e), status=500)

@routes.post("/deluser")
async def deluser(request: web.Request):
    if (not (await check(request, (2, )))):
        return web.Response(status=401)
    try:
        async with aiosqlite.connect("database.sqlite3") as db:
            await db.execute("DELETE FROM users WHERE id=(?)", 
                             [
                                 int((await request.json())["id"])
                             ])
            await db.commit()
        return web.Response()
    except Exception as e:
        return web.Response(body=str(e), status=500)
        
@routes.post("/edituser")
async def edituser(request: web.Request):
    if (not (await check(request, (2, )))):
        return web.Response(status=401)
    try:
        execution = f"""UPDATE users
        SET """
        data = await request.json()
        values = []
        for key in data:
            value = data[key]
            if key == "id":
                continue
            execution += f"{key}=(?) "
            values.append(value)
        execution += f"\nWHERE id=(?)"
        values.append(data["id"])
        async with aiosqlite.connect("database.sqlite3") as db:
            await db.execute(execution, values)
            await db.commit()
        return web.Response()
    except Exception as e:
        return web.Response(body=str(e), status=500)        
        
@routes.post("/getusers")
async def getusers(request: web.Request):
    if (not (await check(request, (2, )))):
        return web.Response(status=401)
    try:
        d = (await request.content.read()).decode()
        print(d)
        data = json.loads(d)
        execution = "SELECT ID, USERNAME, ROLE, NAME FROM users"
        execution += " WHERE "
        sqlitedata = []
        for key in data:
            if (not data[key][1] in (">", ">=", "=>", "=", "<", "<=", "=<", "!=")):
                return web.Response(body="There is something with comparing", status=401)
            if (key == "passwordhash"):
                execution += f"{key}{data[key][1]}(?)"
                sqlitedata.append(hashpass(data[key][0]))
                continue
            execution += f"{key}{data[key][1]}(?) AND "
            if (key in ["id", "role"]):
                sqlitedata.append(int(data[key][0]))
            else:
                sqlitedata.append(data[key][0])
        execution += "1 IS NOT FALSE"
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute(execution, sqlitedata)
            data = await cur.fetchall()
        resp = """<table>
    <thead>
        <tr>
            <th class="header">ID</th>
            <th class="header">USERNAME</th>
            <th class="header">ROLE</th>
            <th class="header">NAME</th>
        </tr>
    </thead>
    <tbody>
"""
        for i in data:
            resp += f"""
        <tr>
            <th class="inner-text">{i[0]}</th>
            <th class="inner-text">{i[1]}</th>
            <th class="inner-text">{i[2]}</th>
            <th class="inner-text">{i[3]}</th>
        </tr>"""
        resp += """
    </tbody>
</table>"""
        return web.Response(body=resp, status=200)
    except Exception as e:
        return web.Response(body=str(e), status=500)
    
@routes.post("/getrooms")
async def getrooms(request: web.Request):
    if (not (await check(request, (2, 1, 0)))):
        return web.Response(status=401)
    try:
        d = (await request.content.read()).decode()
        print(d)
        data = json.loads(d)
        execution = "SELECT NUMBER, ISBUSY, LUXURYLEVEL, NUMBEROFGUESTS, PRICEFORANIGHT, FLOOR, COMMENTS FROM rooms"
        execution += " WHERE "
        sqlitedata = []
        for key in data:
            if (not data[key][1] in (">", ">=", "=>", "=", "<", "<=", "=<", "!=")):
                return web.Response(body="There is something with comparing", status=401)
            execution += f"{key}{data[key][1]}(?) AND "
            if (key in ["number", "isbusy", "luxurylevel", "numberofguests", "priceforanight", "floor"]):
                sqlitedata.append(int(data[key][0]))
            else:
                sqlitedata.append(data[key][0])
        execution += "1 IS NOT FALSE"
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute(execution, sqlitedata)
            data = await cur.fetchall()
        resp = """<table>
    <thead>
        <tr>
            <th class="header">NUMBER</th>
            <th class="header">ISBUSY</th>
            <th class="header">LUXURYLEVEL</th>
            <th class="header">NUMBER OF GUESTS</th>
            <th class="header">PRICE PER NIGHT</th>
            <th class="header">FLOOR</th>
            <th class="header">COMMENTS</th>
        </tr>
    </thead>
    <tbody>
"""
        for i in data:
            resp += f"""
        <tr>
            <th class="inner-text">{i[0]}</th>
            <th class="inner-text">{i[1]}</th>
            <th class="inner-text">{i[2]}</th>
            <th class="inner-text">{i[3]}</th>
            <th class="inner-text">{i[4]}</th>
            <th class="inner-text">{i[5] if len(i) >= 6 else "None"}</th>
            <th class="inner-text">{i[6] if len(i) >= 7 else "None"}</th>
        </tr>"""
        resp += """
    </tbody>
</table>"""
        return web.Response(body=resp, status=200)
    except Exception as e:
        return web.Response(body=str(e), status=500)
    
@routes.post("/getguests")
async def getguests(request: web.Request):
    if (not (await check(request, (2, 1)))):
        return web.Response(status=401)
    try:
        d = (await request.content.read()).decode()
        print(d)
        data = json.loads(d)
        execution = "SELECT ID, FIRSTNAME, LASTNAME, EMAIL, PASSPORT FROM guests"
        execution += " WHERE "
        sqlitedata = []
        for key in data:
            if (not data[key][1] in (">", ">=", "=>", "=", "<", "<=", "=<", "!=")):
                return web.Response(body="There is something with comparing", status=401)
            execution += f"{key}{data[key][1]}(?) AND "
            if (key in ["id", "passport"]):
                sqlitedata.append(int(data[key][0]))
            else:
                sqlitedata.append(data[key][0])
        execution += "1 IS NOT FALSE"
        print(execution)
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute(execution, sqlitedata)
            data = await cur.fetchall()
        resp = """<table>
    <thead>
        <tr>
            <th class="header">ID</th>
            <th class="header">FIRSTNAME</th>
            <th class="header">LASTNAME</th>
            <th class="header">EMAIL</th>
            <th class="header">PASSPORT</th>
        </tr>
    </thead>
    <tbody>
"""
        for i in data:
            resp += f"""
        <tr>
            <th class="inner-text">{i[0]}</th>
            <th class="inner-text">{i[1]}</th>
            <th class="inner-text">{i[2]}</th>
            <th class="inner-text">{i[3]}</th>
            <th class="inner-text">{i[4]}</th>
        </tr>"""
        resp += """
    </tbody>
</table>"""
        return web.Response(body=resp, status=200)
    except Exception as e:
        return web.Response(body=str(e), status=500)
    
@routes.post("/getguestroom")
async def getguestroom(request: web.Request):
    if (not (await check(request, (2, 1, 0)))):
        return web.Response(status=401)
    try:
        d = (await request.content.read()).decode()
        print(d)
        data = json.loads(d)
        execution = "SELECT ID, NUMBEROFROOM, SETTLEMENT, EVICTION, GUESTID, USERWHOADD, ISATTHEHOTEL FROM roomsofguests"
        execution += " WHERE "
        sqlitedata = []
        for key in data:
            if (not data[key][1] in (">", ">=", "=>", "=", "<", "<=", "=<", "!=")):
                return web.Response(body="There is something with comparing", status=401)
            execution += f"{key}{data[key][1]}(?) AND "
            if (key in ["id", "numberofroom", "guestid", "userwhoadd", "isatthehotel"]):
                sqlitedata.append(int(data[key][0]))
            elif (key in ["settlement", "eviction"]):
                sqlitedata.append(int(datetime.datetime.strptime(data[key][0], "%Y-%m-%d").strftime("%s")))
            else:
                sqlitedata.append(data[key][0])
        execution += "1 IS NOT FALSE"
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute(execution, sqlitedata)
            data = await cur.fetchall()
        resp = """<table>
    <thead>
        <tr>
            <th class="header">ID</th>
            <th class="header">NUMBEROFROOM</th>
            <th class="header">SETTLEMENT</th>
            <th class="header">EVICTION</th>
            <th class="header">GUESTID</th>
            <th class="header">USER WHO ADDED</th>
            <th class="header">ISATTHEHOTEL</th>
        </tr>
    </thead>
    <tbody>
"""
        for i in data:
            resp += f"""
        <tr>
            <th class="inner-text">{i[0]}</th>
            <th class="inner-text">{i[1]}</th>
            <th class="inner-text">{i[2]}</th>
            <th class="inner-text">{i[3]}</th>
            <th class="inner-text">{i[4]}</th>
            <th class="inner-text">{i[5]}</th>
            <th class="inner-text">{i[6] if len(i) >= 7 else "None"}</th>
        </tr>"""
        resp += """
    </tbody>
</table>"""
        return web.Response(body=resp, status=200)
    except Exception as e:
        return web.Response(body=str(e), status=500)
        
@routes.post("/addguest")
async def addguest(request: web.Request):
    if (not (await check(request, (2, 1, 0)))):
        return web.Response(status=401)
    try:
        data = await request.json()
        async with aiosqlite.connect("database.sqlite3") as db:
            await db.execute("INSERT INTO guests(firstname, lastname, email, passport) VALUES((?), (?), (?), (?))",
                             [
                                 data["firstname"],
                                 data["lastname"],
                                 data["email"],
                                 int(data["passport"])
                             ])
            cur = await db.execute("SELECT id FROM guests WHERE firstname=(?) AND lastname=(?) AND passport=(?) AND email=(?)",
                                   [
                                       data["firstname"],
                                       data["lastname"],
                                       int(data["passport"]),
                                       data["email"]
                                   ])
            f = await cur.fetchone()
            await db.commit()
        return web.Response(body=f"Done! ID:{f[0]}")
    except Exception as e:
        print(e)
        return web.Response(body=str(e), status=500)
    
@routes.post("/delguest")
async def deluser(request: web.Request):
    if (not (await check(request, (2, 1)))):
        return web.Response(status=401)
    try:
        async with aiosqlite.connect("database.sqlite3") as db:
            await db.execute("DELETE FROM guests WHERE id=(?)", 
                             [
                                 int((await request.json())["id"])
                             ])
            await db.commit()
        return web.Response()
    except Exception as e:
        return web.Response(body=str(e), status=500)
    
@routes.post("/editguests")
async def edituser(request: web.Request):
    if (not (await check(request, (2, 1, 0)))):
        return web.Response(status=401)
    try:
        execution = f"""UPDATE guests
        SET """
        data = await request.json()
        values = []
        for key in data:
            value = data[key]
            if key == "id":
                continue
            execution += f"{key}=(?) "
            values.append(value)
        execution += f"\nWHERE id=(?)"
        values.append(data["id"])
        async with aiosqlite.connect("database.sqlite3") as db:
            await db.execute(execution, values)
            await db.commit()
        return web.Response()
    except Exception as e:
        return web.Response(body=str(e), status=500)
    
@routes.post("/addbook")
async def addguest(request: web.Request):
    if (not (await check(request, (2, 1, 0)))):
        return web.Response(status=401)
    try:
        data = await request.json()
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute("SELECT * FROM roomsofguests WHERE CAST(strftime('%s', eviction) AS INT) > (?)", [int(datetime.datetime.strptime(data["settlement"], "%Y-%m-%d").strftime("%s"))])
            f = await cur.fetchone()
            if (f != None):
                return web.Response(body=f"There is existing book with eviction > new book's settlement")   
            if (not not data.get("isatthehotel")):
                await db.execute("INSERT INTO roomsofguests(numberofroom, settlement, eviction, guestid, userwhoadd, isatthehotel) VALUES((?), (?), (?), (?), (SELECT id FROM users WHERE login=(?) AND passwordhash=(?)) (?))",
                                [
                                    int(data["number-of-room"]),
                                    datetime.datetime.strptime(data["settlement"], "%Y-%m-%d"),
                                    datetime.datetime.strptime(data["eviction"], "%Y-%m-%d"),
                                    int(data["guestid"]),
                                    request.cookies.get("username"),
                                    hashpass(request.cookies.get("password")),
                                    int(data["isatthehotel"])
                                ])
                cur = await db.execute("SELECT id FROM roomsofguests WHERE numberofroom=(?) AND settlement=(?) AND eviction=(?) AND guestid=(?) AND userwhoadd=(SELECT id FROM users WHERE login=(?) AND passwordhash=(?)) AND isatthehotel=(?)",
                                    [
                                        int(data["number-of-room"]),
                                        datetime.datetime.strptime(data["settlement"], "%Y-%m-%d"),
                                        datetime.datetime.strptime(data["eviction"], "%Y-%m-%d"),
                                        int(data["guestid"]),
                                        request.cookies.get("username"),
                                        hashpass(request.cookies.get("password")),
                                        int(data["isatthehotel"])
                                    ])
            else:
                await db.execute("INSERT INTO roomsofguests(numberofroom, settlement, eviction, guestid, userwhoadd, isatthehotel) VALUES((?), (?), (?), (?), (SELECT id FROM users WHERE login=(?) AND passwordhash=(?)) (?))",
                                [
                                    int(data["number-of-room"]),
                                    datetime.datetime.strptime(data["settlement"], "%Y-%m-%d"),
                                    datetime.datetime.strptime(data["eviction"], "%Y-%m-%d"),
                                    int(data["guestid"]),
                                    request.cookies.get("username"),
                                    hashpass(request.cookies.get("password")),
                                ])
                cur = await db.execute("SELECT id FROM roomsofguests WHERE numberofroom=(?) AND settlement=(?) AND eviction=(?) AND guestid=(?) AND userwhoadd=(SELECT id FROM users WHERE login=(?) AND passwordhash=(?))",
                                    [
                                        int(data["number-of-room"]),
                                        datetime.datetime.strptime(data["settlement"], "%Y-%m-%d"),
                                        datetime.datetime.strptime(data["eviction"], "%Y-%m-%d"),
                                        int(data["guestid"]),
                                        request.cookies.get("username"),
                                        hashpass(request.cookies.get("password")),
                                    ])
            f = await cur.fetchone()
            await db.commit()
        return web.Response(body=f"Done! ID:{f[0]}")
    except Exception as e:
        print(e)
        return web.Response(body=str(e), status=500)
                
@routes.post("/editbook")
async def edituser(request: web.Request):
    if (not (await check(request, (2, 1, 0)))):
        return web.Response(status=401)
    try:
        execution = f"""UPDATE roomsofguests
        SET """
        data = await request.json()
        values = []
        for key in data:
            value = data[key]
            if key == "id":
                continue
            execution += f"{key}=(?) "
            values.append(value)
        execution += f"\nWHERE id=(?)"
        values.append(data["id"])
        async with aiosqlite.connect("database.sqlite3") as db:
            cur = await db.execute("SELECT * FROM roomsofguests WHERE CAST(strftime('%s', eviction) AS INT) > (?)", [int(datetime.datetime.strptime(data["settlement"], "%Y-%m-%d").strftime("%s"))])
            f = await cur.fetchone()
            if (f != None):
                return web.Response(body=f"There is existing book with eviction > new book's settlement")   
            await db.execute(execution, values)
            await db.commit()
        return web.Response(body="all is good")
    except Exception as e:
        return web.Response(body=str(e), status=500)   
    
@routes.post("/delguest")
async def deluser(request: web.Request):
    if (not (await check(request, (2, 1, 0)))):
        return web.Response(status=401)
    try:
        async with aiosqlite.connect("database.sqlite3") as db:
            await db.execute("DELETE FROM roomsofguests WHERE id=(?)", 
                             [
                                 int((await request.json())["id"])
                             ])
            await db.commit()
        return web.Response()
    except Exception as e:
        return web.Response(body=str(e), status=500)
        
@routes.get(path="/{key:.*}")
async def all(request: web.Request):
    if (request.cookies.get("username") == None or request.cookies.get("password") == None):
        return web.HTTPFound("/login")
    role = (await get_role(request.cookies.get("username"), request.cookies.get("password")))
    if role == None:
        return web.HTTPFound("/login")
    else:
        if role == 0:
            return web.FileResponse("htmls/main.html")
        elif role == 1:
            return web.FileResponse("htmls/sysmain.html")
        elif role == 2:
            return web.FileResponse("htmls/adminmain.html")
        
async def run():
    if (not os.path.exists("database.sqlite3")):
        async with aiosqlite.connect("database.sqlite3") as db:
            await db.execute("""CREATE TABLE users(ID INT PRIMARY KEY NOT NULL, 
                                                    USERNAME TEXT NOT NULL UNIQUE, 
                                                    PASSWORDHASH BLOB NOT NULL, 
                                                    ROLE INT NOT NULL, 
                                                    NAME TEXT)""")
            await db.execute("""CREATE TABLE rooms(NUMBER INT PRIMARY KEY NOT NULL UNIQUE, 
                                                    ISBUSY INTEGER NOT NULL, 
                                                    LUXURYLEVEL INTEGER NOT NULL, 
                                                    NUMBEROFGUESTS INTEGER NOT NULL, 
                                                    FLOOR INTEGER, 
                                                    COMMENTS TEXT,
                                                    PRICEFORANIGHT FLOAT NOT NULL)""")
            await db.execute("""CREATE TABLE guests(ID INTEGER PRIMARY KEY NOT NULL, 
                                                    FIRSTNAME TEXT NOT NULL, 
                                                    LASTNAME TEXT NOT NULL,
                                                    EMAIL TEXT,
                                                    PASSPORT INTEGER UNIQUE NOT NULL)""")
            await db.execute("""CREATE TABLE roomsofguests(ID INTEGER PRIMARY KEY NOT NULL,
                                                            NUMBEROFROOM INTEGER NOT NULL,
                                                            SETTLEMENT DATETIME NOT NULL,
                                                            EVICTION DATETIME NOT NULL,
                                                            GUESTID INTEGER NOT NULL,
                                                            USERWHOADD INTEGER NOT NULL,
                                                            ISATTHEHOTEL INTEGER)""")
            await db.execute(f"""INSERT INTO users(username, passwordhash, role, name, id) VALUES("admin", (?), 2, "Admin", 0)""", [hashlib.sha256("admin".encode()).hexdigest().encode()])
            await db.commit()
            

asyncio.run(run())
app = web.Application()
app.add_routes(routes)
web.run_app(app, host="localhost")