# Copyright (C) 2023,2024,2025 Giovanni Fulco
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

import cmdtalkplugin
import datetime
import config
import constants

# Func name to method mapper
dispatcher = cmdtalkplugin.Dispatch()


class SimpleMsgProcessor(cmdtalkplugin.Processor):

    def __init__(self, dispatcher):
        super().__init__(dispatcher)
        self.__append_timestamp: bool = config.get_config_param_as_bool(constants.ConfigParam.LOG_WITH_TIMESTAMP)

    def log(self, s):
        if self.__append_timestamp:
            super().log(f"{datetime.datetime.now()} {s}")
        else:
            super().log(s)


msgproc: SimpleMsgProcessor = SimpleMsgProcessor(dispatcher=dispatcher)
