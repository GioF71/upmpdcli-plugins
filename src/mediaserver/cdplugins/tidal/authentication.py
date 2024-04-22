# Copyright (C) 2024 Giovanni Fulco
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from enum import Enum

import constants


class AuthenticationType(Enum):
    OAUTH2 = 1, constants.auth_challenge_type_oauth2
    PKCE = 2, constants.auth_challenge_type_pkce

    def __init__(self,
            num : int,
            auth_type : str):
        self.__num : int = num
        self.__auth_type : str = auth_type

    @property
    def auth_type(self) -> str:
        return self.__auth_type


def convert_authentication_type(conf_val : str) -> AuthenticationType:
    if not conf_val.lower() in [AuthenticationType.OAUTH2.auth_type, AuthenticationType.PKCE.auth_type]:
        raise Exception(f"tidal: invalid authentication type {conf_val}: "
                        f"must be '{AuthenticationType.OAUTH2.auth_type}' or '{AuthenticationType.PKCE.auth_type}'")
    return (AuthenticationType.OAUTH2
        if conf_val.lower() == AuthenticationType.OAUTH2.auth_type
        else AuthenticationType.PKCE)
