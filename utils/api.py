import asyncio
import datetime
import typing

import uvicorn
from fastapi import FastAPI, APIRouter, Header, HTTPException, Request
from discord.ext import commands
import discord
from erm import Bot, management_predicate, is_staff, staff_predicate
from typing import Annotated
from decouple import config

from pydantic import BaseModel

from helpers import MockContext
from utils.utils import tokenGenerator


class Identification(BaseModel):
    license: typing.Optional[typing.Any]
    discord: typing.Optional[typing.Any]
    source: typing.Literal["fivem", "discord"]


async def validate_authorization(bot: Bot, token: str, disable_static_tokens=False):
    # Check static and dynamic tokens
    if not disable_static_tokens:
        static_token = config("API_STATIC_TOKEN")  # Dashboard
        if token == static_token:
            return True
    token_obj = await bot.api_tokens.db.find_one({"token": token})
    if token_obj:
        if int(datetime.datetime.now().timestamp()) < token_obj["expires_at"]:
            return True
        else:
            return False
    else:
        return False


class APIRoutes:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.router = APIRouter()
        for i in dir(self):
           # # print(i)
            if any(
                [i.startswith(a) for a in ("GET_", "POST_", "PATCH_", "DELETE_")]
            ) and not i.startswith("_"):
                x = i.split("_")[0]
                self.router.add_api_route(
                    f"/{i.removeprefix(x+'_')}",
                    getattr(self, i),
                    methods=[i.split("_")[0].upper()],
                )

    def GET_status(self):
        return {"guilds": len(self.bot.guilds), "ping": round(self.bot.latency * 1000)}

    async def POST_get_mutual_guilds(self, request: Request):
        json_data = await request.json()
        guild_ids = json_data.get("guilds")
        if not guild_ids:
            return HTTPException(status_code=400, detail="No guild ids given")

        guilds = []
        for i in guild_ids:
            guild: discord.Guild = self.bot.get_guild(int(i))
            if not guild:
                continue
            if guild.get_member(self.bot.user.id):
                try:
                    icon = guild.icon.with_size(512)
                    icon = icon.with_format("png")
                    icon = str(icon)
                except Exception as e:
                   # # print(e)
                    icon = "https://cdn.discordapp.com/embed/avatars/0.png?size=512"

                guilds.append(
                    {"id": str(guild.id), "name": str(guild.name), "icon_url": icon}
                )

        return {"guilds": guilds}


    async def POST_get_staff_guilds(self, request: Request):
        json_data = await request.json()
        guild_ids = json_data.get("guilds")
        user_id = json_data.get("user")
        if not guild_ids:
            return HTTPException(status_code=400, detail="No guilds specified")

        guilds = []
        for i in guild_ids:
            guild: discord.Guild = self.bot.get_guild(int(i))
            if not guild:
                continue
            if guild.get_member(self.bot.user.id):
                try:
                    icon = guild.icon.with_size(512)
                    icon = icon.with_format("png")
                    icon = str(icon)
                except Exception as e:
                   # # print(e)
                    icon = "https://cdn.discordapp.com/embed/avatars/0.png?size=512"

                try:
                    user = await guild.fetch_member(user_id)
                except:
                    continue
                mock_context = MockContext(bot=self.bot, author=user, guild=guild)

                permission_level = 0
                if await management_predicate(mock_context):
                    permission_level = 2
                elif await staff_predicate(mock_context):
                    permission_level = 1

                if permission_level > 0:
                    guilds.append(
                        {
                            "id": str(guild.id),
                            "name": str(guild.name),
                            "icon_url": icon,
                            "member_count": str(guild.member_count),
                            "permission_level": permission_level,
                        }
                    )

        return guilds

    async def POST_check_staff_level(self, request: Request):
        json_data = await request.json()
        guild_id = json_data.get("guild")
        user_id = json_data.get("user")
        if not guild_id or not user_id:
            return HTTPException(status_code=400, detail="Invalid guild")

        try:
            guild = await self.bot.fetch_guild(guild_id)
        except (discord.Forbidden, discord.HTTPException):
            return HTTPException(status_code=400, detail="Invalid guild")

        try:
            user = await guild.fetch_member(user_id)
        except (discord.Forbidden, discord.HTTPException):
            return {"permission_level": 0}

        mock_context = MockContext(bot=self.bot, author=user, guild=guild)

        permission_level = 0
        if await management_predicate(mock_context):
            permission_level = 2
        elif await staff_predicate(mock_context):
            permission_level = 1

        return {"permission_level": permission_level}

    async def POST_get_guild_settings(self, request: Request):
        json_data = await request.json()
        guild_id = json_data.get("guild")
        if not guild_id:
            return HTTPException(status_code=400, detail="Invalid guild")
        guild: discord.Guild = self.bot.get_guild(int(guild_id))
        settings = await self.bot.settings.find_by_id(guild.id)
        if not settings:
            return HTTPException(status_code=400, detail="Invalid guild")

        return settings

    async def POST_update_guild_settings(self, request: Request):
        json_data = await request.json()
        guild_id = json_data.get("guild")

        for key, value in json_data.items():
            if key == "guild":
                continue
            if isinstance(value, dict):
                settings = await self.bot.settings.find_by_id(guild_id)
                if not settings:
                    return HTTPException(status_code=400, detail="Invalid guild")
                for k, v in value.items():
                    settings[key][k] = v
        await self.bot.settings.update_by_id(settings)

        if not guild_id:
            return HTTPException(status_code=400, detail="Invalid guild")
        guild: discord.Guild = self.bot.get_guild(int(guild_id))
        settings = await self.bot.settings.find_by_id(guild.id)
        if not settings:
            return HTTPException(status_code=404, detail="Guild does not have settings attribute")

        return settings

    async def POST_get_last_warnings(self, request):
        json_data = await request.json()
        guild_id = json_data.get("guild")
        # NOTE: This API is deprecated.
        return HTTPException(status_code=500, detail="This API is deprecated")

        # warning_objects = {}
        # async for document in self.bot.warnings.db.find(
        #         {"Guild": guild_id}
        # ).sort([("$natural", -1)]).limit(10):
        #     warning_objects[document["_id"]] = list(
        #         filter(lambda x: x["Guild"] == guild_id, document["warnings"])
        #     )

        # return warning_objects

    async def GET_get_token(
        self, authorization: Annotated[str | None, Header()], request: Request
    ):
        """

        Generates a token for the API. Requires an unspecified private key.

        :param authorization:
        :param request:
        :return:
        """

        if authorization != config("API_PRIVATE_KEY"):
            raise HTTPException(status_code=401, detail="Invalid authorization")
        has_token = await self.bot.api_tokens.find_by_id(request.client.host)
        if has_token:
            if not int(datetime.datetime.now().timestamp()) > has_token["expires_at"]:
                return has_token
       # # print(request)
        generated = tokenGenerator()
        object = {
            "_id": request.client.host,
            "token": generated,
            "created_at": int(datetime.datetime.now().timestamp()),
            "expires_at": int(datetime.datetime.now().timestamp()) + 2.592e6,
        }

        await self.bot.api_tokens.upsert(object)

        return object

    async def POST_authorize_token(
        self,
        authorization: Annotated[str | None, Header()],
        x_link_string: Annotated[str | None, Header()],
    ):
        """

        Authorizes a token for the API, and links a Discord server to the token. Requires a token and a transfer string, which is placed in the X-Link-String header.

        :param authorization:
        :param x_link_string:
        :return:
        """
        if not authorization:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        if not await validate_authorization(
            self.bot, authorization, disable_static_tokens=True
        ):
            raise HTTPException(
                status_code=401, detail="Invalid or expired authorization."
            )
        token_obj = await self.bot.api_tokens.db.find_one({"token": authorization})

        if not x_link_string:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        link_string_obj = await self.bot.link_strings.db.find_one(
            {"_id": x_link_string}
        )

        if not link_string_obj:
            raise HTTPException(status_code=401, detail="Invalid link string")

        link_string_obj["token"] = authorization
        link_string_obj["ip"] = token_obj["_id"]
        link_string_obj["link_string"] = link_string_obj["_id"]
        await self.bot.link_strings.update_by_id(link_string_obj)

        token_obj["link_string"] = link_string_obj["_id"]
        await self.bot.api_tokens.update_by_id(token_obj)

        return link_string_obj

    async def GET_get_link_string(
        self, authorization: Annotated[str | None, Header()], request: Request
    ):
        """
        Given an authorization token as a header, returns a dictionary with information about the token.

        Parameters:
            authorization (str | None): The authorization token to be verified.
            request (fastapi.Request): The incoming HTTP request.

        Raises:
            HTTPException: If the authorization token is missing, invalid, or has expired.

        Returns:
            dict: A dictionary containing information about the authorization token, such as the token string,
                  its expiration timestamp, and any other associated data.
        """
        if not authorization:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        token_obj = await self.bot.api_tokens.db.find_one({"token": authorization})

        if not token_obj:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        if int(datetime.datetime.now().timestamp()) > token_obj["expires_at"]:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        return token_obj

    async def GET_get_current_token(self, request: Request):
        """
        Given the client host IP, returns a dictionary with information about the token.

        Parameters:
            request (fastapi.Request): The incoming HTTP request.

        Raises:
            HTTPException: If the authorization token is missing, invalid, or has expired.

        Returns:
            dict: A dictionary containing information about the authorization token, such as the token string,
                  its expiration timestamp, and any other associated data.
        """

        token_obj = await self.bot.api_tokens.db.find_one({"_id": request.client.host})
        ## print(token_obj)
        # print(request.client.host)
        if not token_obj:
            raise HTTPException(
                status_code=404, detail="Could not find token associated with IP"
            )

        return token_obj

    async def GET_get_online_staff(
        self, authorization: Annotated[str | None, Header()], request: Request
    ):
        # Use the self.bot.shifts to get all current shifts for the guild ID associated with the link string associated with the token
        if not authorization:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        token_obj = await self.bot.api_tokens.db.find_one({"token": authorization})

        if not token_obj:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        if int(datetime.datetime.now().timestamp()) > token_obj["expires_at"]:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        link_string_obj = await self.bot.link_strings.db.find_one(
            {"_id": token_obj["link_string"]}
        )

        if not link_string_obj:
            raise HTTPException(status_code=401, detail="Invalid link string")

        guild = self.bot.get_guild(link_string_obj["guild"])

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        shifts = []
        async for doc in self.bot.shift_management.shifts.db.find(
            {"data": {"$elemMatch": {"guild": link_string_obj["guild"]}}}
        ):
            item = [
                *list(
                    filter(
                        lambda x: (x or {}).get("guild") == link_string_obj["guild"],
                        doc["data"],
                    )
                )
            ][0]
            item["discord"] = doc["_id"]
            fivem_link = await self.bot.fivem_links.db.find_one(
                {"_id": item["discord"]}
            )
            item["fivem"] = (fivem_link or {}).get("steam_id")
            shifts.append(item)

        return shifts

    async def POST_get_discord(
        self,
        authorization: Annotated[str | None, Header()],
        body: Identification,
        request: Request,
    ):
        if not authorization:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        token_obj = await self.bot.api_tokens.db.find_one({"token": authorization})

        if not token_obj:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        if int(datetime.datetime.now().timestamp()) > token_obj["expires_at"]:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        link_string_obj = await self.bot.link_strings.db.find_one(
            {"_id": token_obj["link_string"]}
        )

        if not link_string_obj:
            raise HTTPException(status_code=401, detail="Invalid link string")

        if not body or not body.license:
            raise HTTPException(status_code=400, detail="Missing license")

        fivem_link = await self.bot.fivem_links.db.find_one({"license": body.license})
        return (
            {"status": "success"}.update(fivem_link)
            if fivem_link
            else {"status": "failed"}
        )

    async def POST_get_fivem(
        self, authorization: Annotated[str | None, Header()], request: Request
    ):
        if not authorization:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        token_obj = await self.bot.api_tokens.db.find_one({"token": authorization})

        if not token_obj:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        if int(datetime.datetime.now().timestamp()) > token_obj["expires_at"]:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        link_string_obj = await self.bot.link_strings.db.find_one(
            {"_id": token_obj["link_string"]}
        )

        if not link_string_obj:
            raise HTTPException(status_code=401, detail="Invalid link string")

        body = await request.json()
        if not body or not body.get("discord_id"):
            raise HTTPException(status_code=400, detail="Missing discord_id")

        fivem_link = await self.bot.fivem_links.db.find_one({"_id": body["discord_id"]})
        return (
            {"status": "success"}.update(fivem_link)
            if fivem_link
            else {"status": "failed"}
        )

    async def POST_duty_on(
        self,
        authorization: Annotated[str | None, Header()],
        identification: Identification,
        request: Request,
    ):
        # print(request)
        # print(await request.json())
        # print("REQUEST ^^")
        if not authorization:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        token_obj = await self.bot.api_tokens.db.find_one({"token": authorization})

        if not token_obj:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        if int(datetime.datetime.now().timestamp()) > token_obj["expires_at"]:
            raise HTTPException(status_code=401, detail="Invalid authorization")

        link_string_obj = await self.bot.link_strings.db.find_one(
            {"_id": token_obj["link_string"]}
        )

        if not link_string_obj:
            raise HTTPException(status_code=401, detail="Invalid link string")

        guild = self.bot.get_guild(link_string_obj["guild"])

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        body = await request.json()

        if not body:
            raise HTTPException(status_code=400, detail="No body provided")

        if not body.get("steam_id"):
            raise HTTPException(status_code=400, detail="No steam ID provided")

        # print(body)
        fivem_link = await self.bot.fivem_links.db.find_one(
            {"steam_id": body["steam_id"]}
        )

        if not fivem_link:
            raise HTTPException(status_code=404, detail="Could not find FiveM link")

        if not fivem_link.get("_id"):
            raise HTTPException(status_code=404, detail="Could not find FiveM link")

        try:
            member = await guild.fetch_member(fivem_link["_id"])
        except discord.NotFound:
            raise HTTPException(status_code=404, detail="Could not find Discord member")

        settings = await self.bot.settings.find_by_id(guild.id)
        if not settings:
            raise HTTPException(status_code=404, detail="Could not find settings")

        if settings.get("shift_types"):
            available_shift_types = []
            for shift_type in settings["shift_types"]:
                available_shift_types.append(shift_type["id"])

        if not body.get("shift_type"):
            await self.bot.shift_management.add_shift_by_user(member, {"guild": guild})
        else:
            if body["shift_type"] not in available_shift_types:
                raise HTTPException(status_code=400, detail="Invalid shift type")
            await self.bot.shift_management.add_shift_by_user(
                member, {"guild": guild, "shift_type": body["shift_type"]}
            )

        return {
            "status": "success",
            "member": member.id,
            "shift_type": body.get("shift_type"),
        }

    async def POST_duty_off(
        self, authorization: Annotated[str | None, Header()], request: Request
    ):
        if not authorization:
            raise HTTPException(status_code=401, detail="Invalid authorization")
        
        if not await validate_authorization(
            self.bot, authorization, disable_static_tokens=False
        ):
            raise HTTPException(
                status_code=401, detail="Invalid or expired authorization."
            )

        token_obj = await self.bot.api_tokens.db.find_one({"token": authorization})

        if token_obj:
            link_string_obj = await self.bot.link_strings.db.find_one(
                {"_id": token_obj["link_string"]}
            )

            if not link_string_obj:
                raise HTTPException(status_code=401, detail="Invalid link string")

            guild = self.bot.get_guild(link_string_obj["guild"])
        else:
            data = await request.json()
            guild = data['guild']

        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")

        body = await request.json()

        if not body:
            raise HTTPException(status_code=400, detail="No body provided")

        if token_obj:
            if not body.get("steam_id"):
                raise HTTPException(status_code=400, detail="No steam ID provided")

            fivem_link = await self.bot.fivem_links.db.find_one(
                {"steam_id": body["steam_id"]}
            )

            if not fivem_link:
                raise HTTPException(status_code=404, detail="Could not find FiveM link")

            if not fivem_link.get("_id"):
                raise HTTPException(status_code=404, detail="Could not find FiveM link")

        try:
            member = await guild.fetch_member(fivem_link["_id"])
        except discord.NotFound:
            raise HTTPException(status_code=404, detail="Could not find Discord member")

        settings = await self.bot.settings.find_by_id(guild.id)
        if not settings:
            raise HTTPException(status_code=404, detail="Could not find settings")

        shifts = await self.bot.shift_management.shifts.find_by_id(member.id)
        if not shifts:
            raise HTTPException(status_code=404, detail="Could not find user shifts")

        associated_shift = list(
            filter(lambda x: (x or {}).get("guild") == guild.id, shifts["data"])
        )
        if not associated_shift or len(associated_shift) == 0:
            raise HTTPException(status_code=404, detail="Could not find user shifts")
        else:
            associated_shift = associated_shift[0]

        await self.bot.shift_management.remove_shift_by_user(
            member, {"guild": guild, "shift": associated_shift}
        )



api = FastAPI()


class ServerAPI(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def start_server(self):
        api.include_router(APIRoutes(self.bot).router)
        self.config = uvicorn.Config("utils.api:api", port=5000, log_level="info", host="0.0.0.0")
        self.server = uvicorn.Server(self.config)
        await self.server.serve()

    async def stop_server(self):
        await self.server.shutdown()

    async def cog_load(self) -> None:
        # asyncio.run_coroutine_threadsafe(self.start_server(), self.bot.loop)
        try:
            await self.start_server()
        except:
            # print('REALLY BAD ERROR.')
            pass
    async def cog_unload(self) -> None:
        await self.stop_server()


async def setup(bot):
    await bot.add_cog(ServerAPI(bot))
